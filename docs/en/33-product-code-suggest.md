# 33 - Product code suggestions for sales staff

*[Tiếng Việt](../33-goi-y-ma-hang.md) · **English***

Since 26.10.220, when a customer messages on Pancake, a Cốc Cốc/Chrome extension shows **which product code the customer is asking about**, with confidence, the reason and live stock. Staff compare and press "Đúng mã này" (this is the right code).

Lookup runs from the surest source down:

| Source | Example |
|---|---|
| **Code in the message** | "price of V33?" |
| **Ad ID** | the customer came from an ad, the message carries Pancake's `ad_ids` |
| **Campaign name** | "CÔNG TY TNHH MTV HALIMI - PAGE NAME - P720" gives code P720 |
| **Post ID** | the customer commented under a post |

Lookup runs on the staff machine from preloaded tables, so it takes milliseconds and costs no AI tokens. Matching by customer photos is not there yet and comes in a later release.

## Install the extension

1. Ask MinMin to "create a pairing code for product suggestions" (tool `javis_goi_y_ma_ma_ghep`): a 6-digit code valid for 15 minutes.
2. In Cốc Cốc open `chrome://extensions`, turn on Developer mode, press "Load unpacked" and pick the `apps/goi-y-ma` folder.
3. Click the extension icon, enter the MinMin address and the 6-digit code, press Ghép máy (pair).

## Loading data

The brain pulls codes, stock and photos from the POS, ads from Meta and posts from Pancake through the connections already set up, then calls `javis_goi_y_ma_nap` in batches. Use `javis_goi_y_ma_tra` to test one message, ad ID or post ID.

Each time staff press "Đúng mã này", MinMin remembers that ad or post ID as that code for next time.
