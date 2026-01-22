/// Pure math utilities for AMM calculations, pricing, and numerical helpers.
/// All functions are stateless and operate on primitive types.

/// Compute the output amount for a constant-product (x*y=k) swap.
///
/// Given `amount_in` tokens deposited into a pool with `reserve_in` and
/// `reserve_out`, returns the number of output tokens received after fees.
///
/// Formula: out = (amount_in * (10000 - fee_bps) * reserve_out)
///                / (reserve_in * 10000 + amount_in * (10000 - fee_bps))
pub fn constant_product_swap(
    amount_in: u64,
    reserve_in: u64,
    reserve_out: u64,
    fee_bps: u16,
) -> u64 {
    if amount_in == 0 || reserve_in == 0 || reserve_out == 0 {
        return 0;
    }
    let amount_in = amount_in as u128;
    let reserve_in = reserve_in as u128;
    let reserve_out = reserve_out as u128;
    let fee_factor = (10000u128).saturating_sub(fee_bps as u128);

    let numerator = amount_in
        .saturating_mul(fee_factor)
        .saturating_mul(reserve_out);
    let denominator = reserve_in
        .saturating_mul(10000u128)
        .saturating_add(amount_in.saturating_mul(fee_factor));

    if denominator == 0 {
        return 0;
    }
    let result = numerator / denominator;
    // Output cannot exceed the reserve.
    if result > reserve_out {
        reserve_out as u64
    } else {
        result as u64
    }
}

/// Compute the input amount required to receive exactly `amount_out` tokens
/// from a constant-product pool.
///
/// Inverse of `constant_product_swap`.
pub fn constant_product_inverse(
    amount_out: u64,
    reserve_in: u64,
    reserve_out: u64,
    fee_bps: u16,
) -> u64 {
    if amount_out == 0 || reserve_in == 0 || reserve_out == 0 {
        return 0;
    }
    if amount_out as u128 >= reserve_out as u128 {
        return u64::MAX; // impossible trade
    }
    let amount_out = amount_out as u128;
    let reserve_in = reserve_in as u128;
    let reserve_out = reserve_out as u128;
    let fee_factor = (10000u128).saturating_sub(fee_bps as u128);

    if fee_factor == 0 {
        return u64::MAX;
    }

    // amount_in = (reserve_in * amount_out * 10000) / ((reserve_out - amount_out) * fee_factor) + 1
    let numerator = reserve_in
        .saturating_mul(amount_out)
        .saturating_mul(10000u128);
    let denominator = (reserve_out.saturating_sub(amount_out)).saturating_mul(fee_factor);

    if denominator == 0 {
        return u64::MAX;
    }
    let result = numerator / denominator + 1;
    if result > u64::MAX as u128 {
        u64::MAX
    } else {
        result as u64
    }
}

/// Calculate the slippage percentage for a swap of `amount` tokens.
///
/// Slippage is defined as 1 - (effective_price / spot_price), expressed as
/// a value between 0.0 and 1.0.
pub fn calculate_slippage(
    amount: u64,
    reserve_a: u64,
    reserve_b: u64,
    fee_bps: u16,
) -> f64 {
    if reserve_a == 0 || reserve_b == 0 || amount == 0 {
        return 0.0;
    }
    let spot_price = reserve_b as f64 / reserve_a as f64;
    let output = constant_product_swap(amount, reserve_a, reserve_b, fee_bps);
    if output == 0 {
        return 1.0;
    }
    let effective_price = output as f64 / amount as f64;
    let slippage = 1.0 - (effective_price / spot_price);
    clamp_f64(slippage, 0.0, 1.0)
}

/// Calculate the price impact of a trade as a fraction (0.0 to 1.0).
///
/// Price impact measures how much the pool price moves, independent of fees.
pub fn calculate_price_impact(amount: u64, reserve_a: u64, reserve_b: u64) -> f64 {
    if reserve_a == 0 || reserve_b == 0 || amount == 0 {
        return 0.0;
    }
    // Price before: reserve_b / reserve_a
    // Price after (ignoring fees): (reserve_b - out) / (reserve_a + amount)
    // where out = amount * reserve_b / (reserve_a + amount)
    let amt = amount as f64;
    let ra = reserve_a as f64;
    let rb = reserve_b as f64;

    let price_before = rb / ra;
    let new_ra = ra + amt;
    let out = amt * rb / new_ra;
    let new_rb = rb - out;
    let price_after = new_rb / new_ra;

    let impact = (price_before - price_after) / price_before;
    clamp_f64(impact, 0.0, 1.0)
}

/// Convert a Q64.64 sqrt-price representation to a floating-point price.
///
/// sqrt_price is stored as a fixed-point number with 64 fractional bits.
/// price = (sqrt_price / 2^64)^2
pub fn sqrt_price_to_price(sqrt_price: u128) -> f64 {
    if sqrt_price == 0 {
        return 0.0;
    }
    let sp = sqrt_price as f64 / (1u128 << 64) as f64;
    sp * sp
}

/// Convert a floating-point price to a Q64.64 sqrt-price representation.
pub fn price_to_sqrt_price(price: f64) -> u128 {
    if price <= 0.0 {
        return 0;
    }
    let sp = price.sqrt();
    let shifted = sp * (1u128 << 64) as f64;
    if shifted >= u128::MAX as f64 {
        u128::MAX
    } else if shifted < 0.0 {
        0
    } else {
        shifted as u128
    }
}

/// Simulate a swap within a concentrated-liquidity pool.
///
/// Returns (amount_out, new_sqrt_price).
///
/// Uses the simplified formula:
///   delta_sqrt_price = amount_in * fee_factor / liquidity
///   new_sqrt_price = sqrt_price + delta_sqrt_price  (buying token B)
///   amount_out = liquidity * delta_sqrt_price / new_sqrt_price * old_sqrt_price
///
/// This is a simplified model; real concentrated-liquidity implementations
/// must handle tick crossings and multiple positions.
pub fn concentrated_liquidity_swap(
    amount: u64,
    liquidity: u128,
    sqrt_price: u128,
    fee_bps: u16,
) -> (u64, u128) {
    if amount == 0 || liquidity == 0 || sqrt_price == 0 {
        return (0, sqrt_price);
    }

    let fee_factor = (10000u64.saturating_sub(fee_bps as u64)) as u128;
    let amount_after_fee = (amount as u128).saturating_mul(fee_factor) / 10000u128;

    // delta_sqrt_price = amount_after_fee * 2^64 / liquidity
    // We scale by 2^64 since sqrt_price is in Q64.64.
    let shift = 1u128 << 64;
    let delta = if liquidity > 0 {
        amount_after_fee.saturating_mul(shift) / liquidity
    } else {
        0
    };

    let new_sqrt_price = sqrt_price.saturating_add(delta);

    // amount_out = liquidity * (1/old_sqrt_price - 1/new_sqrt_price)  (in Q64.64 world)
    // = liquidity * (new_sqrt_price - old_sqrt_price) / (old_sqrt_price * new_sqrt_price / 2^64)
    if new_sqrt_price == 0 {
        return (0, sqrt_price);
    }
    let price_product_shifted = {
        // (sqrt_price * new_sqrt_price) >> 64  to keep in range
        let hi = (sqrt_price >> 32).saturating_mul(new_sqrt_price >> 32);
        if hi == 0 { 1u128 } else { hi }
    };

    let amount_out_128 = liquidity.saturating_mul(delta) / price_product_shifted;
    let amount_out = if amount_out_128 > u64::MAX as u128 {
        u64::MAX
    } else {
        amount_out_128 as u64
    };

    (amount_out, new_sqrt_price)
}

/// Convert basis points to a decimal fraction (e.g., 30 bps -> 0.003).
pub fn bps_to_decimal(bps: u16) -> f64 {
    bps as f64 / 10000.0
}

/// Integer square root using Newton's method.
///
/// Returns the largest integer `r` such that `r*r <= n`.
pub fn isqrt(n: u128) -> u128 {
    if n == 0 {
        return 0;
    }
    if n == 1 {
        return 1;
    }

    // Initial estimate: start from a power-of-two approximation.
    let mut x = 1u128 << ((128 - n.leading_zeros() + 1) / 2);
    loop {
        let x1 = (x + n / x) / 2;
        if x1 >= x {
            break;
        }
        x = x1;
    }
    // Final verification: ensure x*x <= n < (x+1)*(x+1).
    while x.checked_mul(x).map_or(true, |sq| sq > n) {
        x -= 1;
    }
    x
}

/// Weighted average of (value, weight) pairs.
///
/// Returns 0.0 if total weight is zero.
pub fn weighted_average(values: &[(f64, f64)]) -> f64 {
    let total_weight: f64 = values.iter().map(|(_, w)| w).sum();
    if total_weight.abs() < f64::EPSILON {
        return 0.0;
    }
    let weighted_sum: f64 = values.iter().map(|(v, w)| v * w).sum();
    weighted_sum / total_weight
}

/// Standard logistic function: 1 / (1 + e^(-x)).
pub fn logistic(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// Clamp a floating-point value to [min, max].
pub fn clamp_f64(val: f64, min: f64, max: f64) -> f64 {
    if val < min {
        min
    } else if val > max {
        max
    } else {
        val
    }
}

/// Linear interpolation between `a` and `b` at parameter `t` (0.0 to 1.0).
pub fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * clamp_f64(t, 0.0, 1.0)
}

/// Compute the geometric mean of two u64 values, returning a u64.
pub fn geometric_mean(a: u64, b: u64) -> u64 {
    isqrt((a as u128).saturating_mul(b as u128)) as u64
}

#[cfg(test)]
mod tests {
    use super::*;
