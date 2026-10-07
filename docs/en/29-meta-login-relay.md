# Meta login relay

*[Tiếng Việt](../29-tram-dang-nhap-meta.md) · **English***

The Meta login relay lets MinMin users click **Continue with Facebook** instead of creating their own Facebook App and pasting an App ID, App Secret and redirect URI. This page is for the **relay operator** (the MinMin publisher). Regular users only see an extra button in the Meta Ads and Facebook Page connection dialogs.

## How it works

1. The user clicks **Continue with Facebook** on the Connections page.
2. Their MinMin server sends a signed request to the relay, which answers with a confirmation page.
3. The confirmation page shows which MinMin server will receive the token and which permissions it gets. The user clicks **Continue with Facebook**.
4. Facebook returns the authorization code to the relay, the only place that holds the App Secret, which exchanges it for a long-lived token.
5. The relay encrypts the token for that server only and redirects the browser back. The server fetches the encrypted blob, decrypts it and stores it like any other connection.
6. About 60 days later the server asks the relay to extend the token.

The relay stores no tokens; the encrypted blob lives in memory for at most 5 minutes. The token does pass through the relay's memory during the exchange, and the privacy page says so. Users who prefer can still create their own app.

## Setting up the relay

1. Create a **Business** app at developers.facebook.com, add Facebook Login (or Facebook Login for Business) and the Marketing API.
2. Valid OAuth Redirect URIs: `https://<your-domain>/mt/ve`. App domain: your domain. Privacy policy: `/mt/chinh-sach`. Terms: `/mt/dieu-khoan`. Data deletion instructions: `/mt/xoa-du-lieu`.
3. Keep **Require App Secret** OFF: user servers call the Graph API directly and cannot compute `appsecret_proof`.
4. Put `JAVIS_META_TRAM_APP_ID`, `JAVIS_META_TRAM_APP_SECRET`, `JAVIS_META_TRAM_GOC` and `JAVIS_META_TRAM_LIEN_HE` in the `.env` next to `docker-compose.yml`, then `docker compose up -d`. `/mt/thong-tin` must report `"bat": true`.
5. Before App Review only app Admins, Developers and Testers can sign in. Add trusted users as Testers.
6. Complete Business Verification, request Advanced Access for `ads_read`, `ads_management`, `business_management`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_engagement`, `read_insights`, with a screencast of the flow. Then switch to Live and request Ads Management Standard Access (at least 1,500 Marketing API calls in 30 days, error rate under 10%).
7. If Meta requires Facebook Login for Business, create a configuration and set `JAVIS_META_TRAM_CONFIG_ID`.

## Limits

- API rate limits are shared across every user of the app.
- If the relay is down, nobody can sign in or extend a token; existing tokens keep working until they expire.
- Meta may restrict the whole app if one user abuses it. The relay terms forbid this and the relay can block a server, but the shared-app risk is real.

On user servers, `JAVIS_META_TRAM` points to the relay (default `https://minmin.elaria.cloud`); set it to `off` to hide the quick sign-in.
