# 30 - Multi-account connectors: marketplaces, shipping, payments, TikTok Ads, Zalo OA

*[Tiếng Việt](../30-ket-noi-da-tai-khoan.md) · **English***

From 26.10.115 the **Connections** page has 10 more platforms, and 26.10.116 adds 12 more. What they share: **one connection
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
| Sales | Tiki | 1 shop | Orders, products, stock (from 26.10.116) |
| Sales | Haravan, Sapo | 1 store | Orders, products, customers, stock |
| Sales | KiotViet, Nhanh.vn | 1 account | Branches/warehouses, products, stock, orders, invoices, customers |
| Shipping | Viettel Post, Ahamove | 1 account | Fees, tracking, create and cancel shipments |
| Shipping | J&T Express | 1 partner account | Tracking, cancel (J&T has no public create-order API) |
| Social | Instagram | 1 professional account | Publish images, carousels, Reels; read posts, comments, insights |
| Social | Threads | 1 profile | Publish text, image, video, carousel; replies; insights |
| Social | X (Twitter) | 1 account | Post, reply, delete; recent posts (X charges per post) |
| Invoices & tax | MISA meInvoice | 1 tax code | Invoice templates, invoice status, view link |

## Safety

- Every new connection starts **Read only**. Creating shipments, payment links, toggling ads or
  sending Zalo messages needs that connection raised to **Full access** by you.
- Marketplaces, sales software and MISA meInvoice are **read only**, even at Full access.
- **Zalo Ads is not available**: Zalo publishes no ads reporting API. Export reports from Zalo Ads Manager and send them to MinMin for now.
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

## Balance alerts (Techcombank via Casso)

When a customer transfers money into your account, MinMin tells you at once: the bell, browser
push, your Telegram, and staff groups if you want. Open the **Balance alerts** page (Connections
group on the sidebar) and follow it:

1. Sign in to Casso Flow and link your Techcombank account (Banks, Add account).
2. In Casso: **Integrations > Webhook > Add webhook V2**, paste the MinMin address shown in step 2
   (the **Copy** button). The address carries its own secret; if it leaks, press **Change address**.
3. Copy the **security key** Casso gives you, paste it into step 3 and **Save**. Without the key
   MinMin rejects every transaction, because each one must carry a valid signature.
4. Save the webhook in Casso and press **Test call**: a "test" transaction appears and is announced.

Options: alert only for money in (the default), only from a minimum amount, and **also notify** a
Telegram group chat id (it must already be in the bot's allow list) or `zalo:<id>`. When Casso
resends a transaction, MinMin announces it once. Ask MinMin "how much came in today" and it reads
the transaction list directly.

## Certification before shipping

Each platform has its own tests for signing and calling the API (`tests/python/test_<name>_mcp.py`),
plus one shared gate, `tests/python/test_ket_noi_noi_bo.py`, that every bridge must pass: every
tool classified for permissions, dangerous tools blocked at lower levels, no network call when
keys are missing, no secret leaked in any error, no token mixing between two accounts. The tests
run offline, so the first time you use a real account, press **Test** on the Connections page.
