/** Maximum character count for workspace descriptions */
export const WORKSPACE_DESCRIPTION_MAX_CHARS = 3000

// -- File sharing pricing (source of truth: server/rapidly/config.py) --

/** Minimum price in cents for paid file shares. Backend: FILE_SHARING_MIN_PRICE_CENTS */
export const FILE_SHARING_MIN_PRICE_CENTS = 100

/** Maximum price in cents for paid file shares. Backend: FILE_SHARING_MAX_PRICE_CENTS */
export const FILE_SHARING_MAX_PRICE_CENTS = 100_000_000
