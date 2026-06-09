# Contractor Invoice Management - Deployment Guide

## PythonAnywhere Deployment

### Step 1: Create Account
1. Go to **https://www.pythonanywhere.com** and sign up for a **free Beginner account**
2. Your app will be live at: `https://YOUR_USERNAME.pythonanywhere.com`

### Step 2: Upload Code
1. Open a **Bash console** from the PythonAnywhere Dashboard
2. Run these commands:

```bash
# Clone or upload your code
mkdir -p ~/contractor-invoice-app
```

3. Go to **Files** tab → Navigate to `/home/YOUR_USERNAME/contractor-invoice-app/`
4. Upload ALL files from the `backend/` folder using the upload button
   - Or use git: `git clone YOUR_REPO_URL ~/contractor-invoice-app`

### Step 3: Install Dependencies
In the Bash console:
```bash
cd ~/contractor-invoice-app
pip install --user fastapi uvicorn sqlalchemy pydantic pydantic-settings python-multipart openpyxl pandas pdfplumber
```

### Step 4: Create WSGI File
1. Go to **Web** tab → Click **Add a new web app**
2. Choose **Manual configuration** → **Python 3.10+**
3. In the WSGI configuration file, replace ALL content with:

```python
import sys
import os

path = '/home/YOUR_USERNAME/contractor-invoice-app'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)
os.environ['DEBUG'] = 'false'

from app.main import app

# PythonAnywhere uses WSGI, FastAPI needs ASGI adapter
from starlette.middleware.wsgi import WSGIMiddleware
```

### Step 5: Set Static Files
In the **Web** tab, under **Static files**:
- URL: `/static/` → Directory: `/home/YOUR_USERNAME/contractor-invoice-app/static/`

### Step 6: Reload
Click the **Reload** button on the Web tab.

Your app is now live at `https://YOUR_USERNAME.pythonanywhere.com`!
