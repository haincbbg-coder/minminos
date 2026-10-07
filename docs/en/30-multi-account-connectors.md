# 30 - Multi-account connectors: marketplaces, shipping, payments, TikTok Ads, Zalo OA

*[Tiếng Việt](../30-ket-noi-da-tai-khoan.md) · **English***

From 26.10.115 the **Connections** page has 10 more platforms. What they share: **one connection
is one account**. Three Shopee shops means three Shopee connections; two GHN accounts means two
GHN connections. MinMin gives each connection its own name, so "today's orders for the MeiMei
shop" reaches the right shop.

Nothing to install: MinMin calls each platform's API from Python, on a home PC or a VPS alike.

## The list

| Group | Platform | One connection is | What it does |
|---|---|---|---|
| Sales | Shopee | 1 shop | Orders, order detail, net payout, products |
| Sales | TikTok Shop | 1 shop | Orders, order detail, products |
| Sales | Lazada | 1 shop | Orders, order items, products |
| Shipping | GHN | 1 account (many stores) | Fees, tracking, create and cancel shipments |
| Shipping | GHTK | 1 account | Fees, tracking, create and cancel shipments |
| Payments | SePay | 1 account (many banks) | Transactions, money in and out today |
| Payments | Casso | 1 business | Transactions, money in and out summary |
| Payments | payOS | 1 payment channel | Create, view and cancel VietQR payment links |
| Ads | TikTok Ads | 1 authorization (many ad accounts) | Campaigns, reports, pause/enable, budgets |
| Messaging | Zalo OA | 1 Official Account | Conversations, followers, customer-care messages |

## Safety

- Every new connection starts **Read only**. Creating shipments, payment links, toggling ads or
  sending Zalo messages needs that connection raised to **Full access** by you.
- The three marketplaces are **read only** in this release, even at Full access.
- Keys, app secrets and tokens are **encrypted** at rest and masked out of every answer, log and
  Telegram message, even when a platform echoes a token back in an error.
- Shopee, Lazada, TikTok Shop and Zalo OA tokens expire. MinMin refreshes and saves them, once
  per connection even when several jobs run at the same moment, so single-use refresh tokens
  are never spent twice.
- payOS response signatures are verified: a tampered response is reported as an error.

## Authorizing a shop (Shopee, Lazada, TikTok Shop, Zalo OA)

1. Create an app on the platform's developer site (the steps are in the connection form).
2. Paste the app keys into the connection and save.
3. Ask MinMin to "create the Shopee authorization link" (or Lazada, Zalo OA), open it, sign in, agree.
4. Copy the `code` from the returned address into **Authorization code** and save.

A second shop: add a new connection, reuse the app keys, only the code (and Shop ID on Shopee) differ.

## Certification before shipping

Each platform has its own tests for signing and calling the API (`tests/python/test_<name>_mcp.py`),
plus one shared gate, `tests/python/test_ket_noi_noi_bo.py`, that every bridge must pass: every
tool classified for permissions, dangerous tools blocked at lower levels, no network call when
keys are missing, no secret leaked in any error, no token mixing between two accounts. The tests
run offline, so the first time you use a real account, press **Test** on the Connections page.
