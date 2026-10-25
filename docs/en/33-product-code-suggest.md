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

The first three sources run on the staff machine from preloaded tables, so they take milliseconds and cost no AI tokens.

**Customer photos** (since 26.10.225): the extension sends the latest photo to MinMin. MinMin shortlists by colour (no tokens), then asks ChatGPT on the signed-in plan to look at the customer photo next to a sheet of sample photos of the ~36 closest codes and pick up to 5. It takes a few seconds, one call per photo, and a photo already compared costs nothing. There is a daily cap (default 500, set with the `JAVIS_GOI_Y_ANH_TRAN_NGAY` variable). Click a thumbnail to compare another photo. Pressing "Đúng mã này" makes MinMin remember that photo as that code, so the shortlist gets sharper. ChatGPT must be signed in on the Models page.

## Install the extension

1. Ask MinMin to "create a pairing code for product suggestions" (tool `javis_goi_y_ma_ma_ghep`): a 6-digit code valid for 15 minutes.
2. In Cốc Cốc open `chrome://extensions`, turn on Developer mode, press "Load unpacked" and pick the `apps/goi-y-ma` folder.
3. Click the extension icon, enter the MinMin address and the 6-digit code, press Ghép máy (pair).

## Loading data

The brain pulls codes, stock and photos from the POS, ads from Meta and posts from Pancake through the connections already set up, then calls `javis_goi_y_ma_nap` in batches. Use `javis_goi_y_ma_tra` to test one message, ad ID or post ID.

You can load hundreds of codes at once from a `.json` file in the brain: `javis_goi_y_ma_nap` with `tep: "attachments/file-name.json"`. A compact code list like `"P664:508"` (code:stock) works too.

After loading codes, ask MinMin to run `javis_goi_y_ma_hoc_anh` once to learn the sample photos (downloaded from the POS, safe to rerun, only learns codes it has not seen).

Each time staff press "Đúng mã này", MinMin remembers that ad or post ID as that code for next time.

**Ads**: Pancake records the ad id in a message of type `ad_click`. The extension reads that id and the ad text (a code mentioned there is suggested directly). If the ad is not in the table yet, it compares the ad image with the sample photos. Stickers and the like button are not treated as photos.
