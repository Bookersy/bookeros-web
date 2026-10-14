# Building BookerOS Web on GitHub

GitHub builds the ISO for you (with Firefox included) every time you upload a
change, and puts it on the **Releases** page as a single `bookeros-web.iso` download.

## One-time setup

1. Sign up at **github.com** (free).
2. Click **+** (top right) → **New repository**.
   - Name: `bookeros-web`
   - **Public** (builds are free and unlimited; Private also works, with 2,000 free build minutes a month)
   - Leave every box unticked → **Create repository**.
3. On the new, empty repository page, click **uploading an existing file**.
4. Unzip `bookeros-web-source.zip`, open the `webos` folder, select **everything inside it**
   (`.github`, `shell`, `system`, `build.sh`, `README.md`, `GITHUB-SETUP.md`) and drag it all onto the page.
5. Click **Commit changes**.

That starts the first build straight away.

> If the `.github` folder didn't upload (it won't appear in the file list), click
> **Add file → Create new file**, type `.github/workflows/build.yml` as the name,
> paste in the contents of `webos/.github/workflows/build.yml`, and click **Commit changes**.

## Getting the ISO

1. Open the **Actions** tab to watch the build. It takes about 15–25 minutes; a green tick means it's done.
2. Open the **Releases** section (right-hand side of the repository's main page), or go straight to
   `https://github.com/YOUR-USERNAME/bookeros-web/releases/latest`.
3. Download **bookeros-web.iso** and attach it to your VirtualBox VM.

## Making changes later

Upload changed files the same way (**Add file → Upload files**, drag them in, **Commit changes**).
Keep the folder structure: for example, an updated `shell/shell.py` goes inside the `shell` folder
(open that folder on GitHub first, then upload). Each upload makes a new build and release.

To rebuild without changing anything: **Actions → Build ISO → Run workflow**.

## If a build fails

Open the failed run in the **Actions** tab, click the red step, and copy the last
20 or so lines of the log to Claude.
