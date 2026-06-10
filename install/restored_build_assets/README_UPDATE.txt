# Arrow Limousine App Update Instructions

1. Ensure the full app folder (including `.venv`) is present in your Dropbox `install/limo` folder.
2. Copy `one_click_update.bat` to your Dropbox `updates` folder.
3. On the remote PC, run `one_click_update.bat` from the Dropbox `updates` folder.
   - This will backup the current install, remove old files, and copy the new app (including `.venv`) to `Y:\limo`.
4. Launch the app using `START_ARROW_LIMO.bat` in `Y:\limo`.

**Note:** This script will stop the running app, backup the old install, and fully replace the app folder for a clean update.
