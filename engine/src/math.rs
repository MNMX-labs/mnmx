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
