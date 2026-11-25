# KhabarNazar: manual test checklist (phone and web)

Use this alongside `FULL_TEST_REPORT_2026-11-24.md`. It covers what the automated pass could not:
the native app in Expo Go (Android and iPhone), the camera roll, rotation, network loss and
backgrounding. Fill in the last two columns.

**Run on 2026-11-25 by Claude in a browser** (Expo web at phone size against a throwaway backend with the real models; results in `backend/tests/full_pass/results_manual_2026-11-25.json`, screenshots `MC-*.png`): 28 Pass (3 of them emulated), 2 Known limitation, 2 Blocked (16, 19: need a real phone). Steps 15, 16, 19, 21 and 22 are still worth repeating on a real phone in Expo Go.

**Before you start**

- Start the backend on the PC with your normal setup (`uvicorn app.main:app --host 0.0.0.0 --port 8000`,
  local PostgreSQL) and wait until `http://<PC-IP>:8000/health` shows `"ready": true` under `models`
  (about a minute after start-up).
- Start the app: `npx expo start`, scan the QR code with Expo Go (phone on the same Wi-Fi).
- Web: `npx expo start --web`, open the printed URL in Chrome (and Safari on iPhone, if you test the web app there).
- Have two accounts ready: a normal user, and an admin (register it, then run
  `.\.venv\Scripts\python.exe scripts\set_user_role.py <email> admin` in `backend/`).
- Copy the images in `backend/tests/full_pass/images/` to the phone (AirDrop, Google Drive, USB or email them to yourself).
- Checks take time on the PC's CPU: Urdu 1–3 s, Roman Urdu up to about 15 s, images 6–15 s. That is not a failure.
- Inputs below come from `backend/tests/full_pass/text_inputs.json` (IDs in brackets).

| # | Area | Do this (exact input) | You should see | Pass/Fail | Notes |
|---|------|------------------------|----------------|-----------|-------|
| 1 | Splash | Open the app signed out. | The KhabarNazar start screen (purple, "News at a Glance…"; on a phone "Loading your session…" may flash), then the **Welcome back** sign-in page. | Pass | Web: dark frame, branded start screen, then /login. "Loading your session…" text not seen on web. |
| 2 | Register | Tap **Create an account**. Name `Test Phone`, a new email, password `Password123!`, confirm `Password123!x`. Tap **Create account**. | A "Passwords do not match" message; you stay on the form. | Pass |  |
| 3 | Register | Fix the confirmation to `Password123!` and tap **Create account**. | You are signed in and land on the **Check** (home) tab. Register the same email again from a signed-out state: "An account with this email already exists." | Pass | Duplicate email message shown. |
| 4 | Login | Sign out, then sign in with the right email and password `WrongPass1`. | "Incorrect email or password entered." Same message for an email that does not exist. | Pass | Same message for both. |
| 5 | Forgot password | On sign-in, tap **Forgot password?**, enter your email, tap **Continue**. | A message that password reset is not available yet (known limitation 5). | Known limitation | "not available" message shown. |
| 6 | Login | Sign in correctly as the normal user. | The Check tab; no admin tools in Profile. Signing in as the admin shows **Moderation desk**. | Pass | Moderation desk only for the admin. |
| 7 | Empty check | On Check, leave the box empty and tap **Analyze**. | The check does not start; a prompt to enter text (or a disabled button). | Pass | Analyze is greyed out. |
| 8 | Urdu text | Paste [U02] `حکومت نے اعلان کیا ہے کہ ملک بھر میں سات دن کے لیے انٹرنیٹ سروس بند کر دی جائے گی۔` and tap **Analyze**. | The button shows it is busy while waiting. The result has a **Verdict**, **Score**, **Fake-news risk**, the claim shown **right-to-left in Nastaliq**, "Detected language: Urdu script", and **Why this result** with highlighted Urdu words. | Pass | Claim right-to-left in Nastaliq; all parts present. |
| 9 | Roman Urdu | Paste [R02] `Hukoomat ne elan kiya hai ke mulk bhar mein saat din ke liye internet service band kar di jayegi.` | A Real/Fake verdict with score; highlighted Roman Urdu words; takes up to about 15 s. | Pass |  |
| 10 | English | Paste [E01] `The government has announced that all schools will remain closed for a week because of heavy rain.` | A verdict plus the note that results for English text are less reliable (known limitation 4). | Known limitation | "less reliable" note shown. |
| 11 | Long Urdu | Paste [UL1] (the 200-word text in `text_inputs.json`). | A verdict with the note "Long articles are checked as a whole"; highlighted words. | Pass | "checked as a whole" note shown. |
| 12 | Mixed | Paste [M03] `حکومت نے اعلان کیا hai ke kal se tamam schools band rahenge aur imtihanat agle mahine honge` | A verdict and the note that the text mixes scripts and was checked as Roman Urdu. | Pass | Mixed-script note shown. |
| 13 | Rejected text | Paste [X03] `ab` and tap **Analyze**. Then paste only spaces. | **Analyze** stays greyed out (it needs at least 3 characters), so nothing is sent; nothing new appears in History. | Pass | Analyze greyed out for `ab` and for spaces; History unchanged. |
| 14 | No letters | Paste [X08] `1234567890`. | **Uncertain** with no score and a message that there are no words to classify. | Pass | Uncertain, no score, "no words to classify". |
| 15 | Rotate during analysis | Paste [R06] and tap **Analyze**, then rotate the phone while it is busy. | The analysis still finishes and the result opens; nothing is submitted twice (check History). | Pass (emulated) | Browser switched to landscape mid-check; result opened; one submission. |
| 16 | Image from camera roll (iPhone HEIC) | Tap **Gallery**, pick a normal photo you took with the iPhone camera (HEIC). | The picker hands the app a JPEG; the upload is accepted (not "Unsupported image format"). Note what happens if it is refused. | Blocked | Needs an iPhone camera roll; not testable in a browser. |
| 17 | Image with text | Pick `urdu_headline.png` (or take a photo of it on a screen), then tap the **×** on the preview and pick `roman_headline.png`; tap **Analyze**. | The second picture is the one analysed. The **news verdict comes first**, then **Image authenticity (separate from the verdict above)** in a neutral colour with the screenshot warning, then the Grad-CAM heatmap captioned as coming from the detector's ResNet18 model. | Pass | Second image analysed; verdict first; ResNet18 caption. |
| 18 | Image without text | Pick `local_fox_no_text.jpg`. | No fake-news verdict ("No news claim was checked"), Image authenticity with a percentage, and a heatmap. | Pass | "No news claim was checked"; authenticity %; heatmap. |
| 19 | Camera | Tap **Camera** (phone only), photograph printed or on-screen text. | Permission prompt the first time; the photo is analysed like a gallery image. | Blocked | Camera button exists only in the phone app. |
| 20 | Rejected image | Pick `format.gif` or the 11 MB `format_just_over_10mb.png`. | "Choose a JPG, PNG, or WEBP image." / "This image is larger than …"; nothing new in History. | Pass | Both rejected with clear messages; History unchanged. |
| 21 | Network loss | Start an image check, then turn on Airplane mode before it finishes. | An error such as "Cannot reach the backend at …" (no crash, no endless spinner). Turn the network back on and retry: it works. | Pass (emulated) | Upload connection dropped mid-request: "Cannot reach the backend at …", button usable; retry worked. Whole-browser offline on the Expo *dev* web server crashes the next screen's lazy load (dev only). |
| 22 | Background and return | Start a Roman Urdu check, switch to another app for 20 s, come back. | Either the result is shown or a clear error; the app does not restart or sign you out. | Pass (emulated) | Page frozen 20 s mid-check: result shown, still signed in. |
| 23 | History | Open **History**. | Your checks newest first with labels; tap one to open its full result. A brand-new account shows the empty state. | Pass | Newest first; tapping opens the result; empty state for a new account. |
| 24 | Dispute | Open the Urdu result from step 8, tap **Dispute this result**, type `short`, then a real reason and the link `geo.tv/news/12345`; submit. | First "Please write at least 10 characters"; then the dispute is saved, the result shows **Waiting for an administrator to review this dispute**. | Pass | Minimum-length hint, then "Waiting for an administrator…". |
| 25 | Admin queue | Sign in as the admin, open **Moderation desk** / admin disputes. | The pending dispute from step 24 is listed. | Pass |  |
| 26 | Admin review | Open it, tap **Override verdict** with an empty comment. Then write `Checked with the ministry`, choose **Credible**, tap **Override verdict**. | First "A comment is required (at least 3 characters)"; then "The decision was recorded." | Pass | Comment-required message, then "The decision was recorded." |
| 27 | User sees decision | Sign back in as the normal user; open the disputed result and History. | Final label **Credible** marked as the admin's decision, with the admin's comment. | Pass | Credible, "set by an administrator", comment, AI's original estimate. |
| 28 | Admin lists | As admin, open the all-submissions list and the dashboard. | Everyone's checks with their emails; the filter chips (All, Misleading, Uncertain, Credible, Disputed, Text, Images) narrow the list; counts on the dashboard. | Pass | Filters checked: Credible, Disputed, Images, All. |
| 29 | Non-admin | As the normal user, open `/admin` on web (type it in the address bar). | You are sent back to the Check tab. | Pass | Sent to /. |
| 30 | Profile | Profile → **My profile**, **Change profile photo** (pick any photo), then **Sign out** → confirm. | Name and email shown; the photo changes locally; after sign-out you are on the sign-in page and Back does not return to protected pages. | Pass | Photo changes; after sign-out /history and Back go to sign-in. |
| 31 | Session reload (web) | Signed in on web, open History and press F5. Then, signed out, open `/history` directly. | Reload keeps you on History; signed out you are sent to sign-in. | Pass |  |
| 32 | Layout | On the phone and in a narrow browser window, scroll the long Urdu result and the image result. | Text wraps, nothing is cut off or scrolls sideways; Urdu stays right-to-left. | Pass | 390 px and 320 px: no sideways scroll; Urdu right-to-left. |
