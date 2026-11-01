# Install and use the PWA

For the full PWA experience, use **HTTPS with a certificate trusted by the device**.
This applies even when the Linux server and phone share a LAN or VPN. An HTTP
address on a private network is not a secure context for service workers.

This is not only an Apple restriction: browsers reserve service workers for secure
contexts. The `http://localhost` exception is for development on the same device;
it does not make a remote server's private IP a secure origin.
[Service Worker documentation](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

## iPhone and iPad

Open your HTTPS address in Safari, choose **Share → Add to Home Screen**, then
launch the new icon. Adding an HTTP bookmark to the Home Screen does not enable
protected PWA features.

Web Push on iOS/iPadOS requires version 16.4 or later and a Home Screen web app.
Permission must follow a user action.
[WebKit requirements](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
The server operator must also enable push, configure a valid VAPID contact/origin
and allow outbound HTTPS to notification providers.

## Other browsers

Open the HTTPS site and use the browser's install command where available.
The ordinary browser interface remains available even without installation.
Installation prompts and push support depend on the browser and operating system.

## Connection, updates and layout

The PWA caches the static app shell. It does not cache authenticated API responses
or queue offline expense entries. Viewing current data and saving changes require
a reachable server. Save open forms before accepting an available app update.

Theme and accent are local browser preferences. Navigation appears at the bottom
below 768 px and on the right at larger widths. The overview uses two columns from
1024 px. Standard iPhone and iPhone Duo closed/open layouts follow available space;
the web app does not need to detect a hinge or folding angle.

HTTPS and certificates are managed entirely by your [external proxy](proxy.md).
