#!/usr/bin/env python3
"""
Production Screen Recording App with Google Drive Integration
Uploads recordings to Google Drive and generates shareable links
"""

from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import os
import json
import hashlib
import secrets
import time
import uuid
from functools import wraps
from datetime import datetime, timedelta
import io

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Environment variables
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'change-in-production')

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '1w-AJOAMwSa8rU0MEdF1wwcnGhOb97m5Q')  # Blueshift Support - screen recordings
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')  # Service account JSON as string

# Import Google Drive libraries
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2 import service_account
    google_drive_available = True
    print("✅ Google Drive libraries imported successfully")
except ImportError as e:
    google_drive_available = False
    print(f"❌ Google Drive import error: {e}")

def get_admin_hash():
    return hashlib.pbkdf2_hmac('sha256', ADMIN_PASSWORD.encode(), b'admin-salt', 100000).hex()

def verify_admin_password(username, password):
    if username != ADMIN_USERNAME:
        return False
    hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode(), b'admin-salt', 100000).hex()
    return secrets.compare_digest(get_admin_hash(), hashed_password)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            if request.is_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def upload_to_google_drive(file_data, filename):
    """Upload file to Google Drive and return shareable link"""
    try:
        print(f"🔍 Starting Google Drive upload for {filename}")
        
        if not GOOGLE_CREDENTIALS_JSON:
            error_msg = "Google Drive credentials not configured"
            print(f"❌ {error_msg}")
            return None, error_msg
        
        print(f"✅ Credentials found, parsing JSON...")
        
        # Parse credentials JSON
        credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        print(f"✅ JSON parsed, client_email: {credentials_info.get('client_email', 'NOT FOUND')}")
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        print(f"✅ Credentials created")
        
        # Build Drive service
        service = build('drive', 'v3', credentials=credentials)
        print(f"✅ Drive service built")
        
        # File metadata
        file_metadata = {
            'name': filename,
            'description': f'Blueshift Support Screen Recording - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        }
        
        # If folder ID is specified, upload to that folder
        if GOOGLE_DRIVE_FOLDER_ID:
            file_metadata['parents'] = [GOOGLE_DRIVE_FOLDER_ID]
            print(f"✅ Uploading to folder: {GOOGLE_DRIVE_FOLDER_ID}")
        else:
            print(f"⚠️ No folder ID specified, uploading to root")
        
        print(f"✅ File size: {len(file_data)} bytes")
        
        # Upload file
        media = MediaIoBaseUpload(
            io.BytesIO(file_data), 
            mimetype='video/webm',
            resumable=True
        )
        print(f"✅ Media upload object created")
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"✅ File uploaded to Drive")
        
        file_id = file.get('id')
        print(f"✅ File ID: {file_id}")
        
        # Make file publicly viewable (anyone with link can view)
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(fileId=file_id, body=permission).execute()
        print(f"✅ Permissions set to public")
        
        # Generate shareable link
        shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        print(f"✅ Shareable link created: {shareable_link}")
        
        return shareable_link, None
        
    except Exception as e:
        error_msg = f"Google Drive upload error: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return None, error_msg

# Recording storage log
recording_log = []

# Templates
CUSTOMER_INTERFACE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Record Your Issue - Blueshift Support</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 900px;
            margin: 0 auto;
            background: white; 
            padding: 40px; 
            border-radius: 15px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 30px;
            border-bottom: 3px solid #667eea;
        }
        .header h1 {
            color: #333;
            margin: 0;
            font-size: 2.5em;
        }
        .header p {
            color: #666;
            font-size: 1.2em;
            margin: 10px 0;
        }
        .step-guide {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .step {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border-left: 4px solid #667eea;
        }
        .step-number {
            background: #667eea;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 15px auto;
            font-weight: bold;
            font-size: 1.2em;
        }
        .record-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin: 30px 0;
            text-align: center;
        }
        .record-btn {
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 20px 40px;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            font-size: 20px;
            margin: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(220,53,69,0.3);
            min-width: 250px;
        }
        .record-btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(220,53,69,0.4);
        }
        .record-btn:disabled { 
            background: #6c757d; 
            cursor: not-allowed; 
            transform: none;
            box-shadow: none;
        }
        .record-btn.recording {
            background: linear-gradient(135deg, #28a745, #20c997);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        .recording-status {
            display: none;
            color: #dc3545;
            font-weight: bold;
            margin: 20px 0;
            font-size: 18px;
        }
        .recording-status.active { display: block; }
        .timer {
            font-family: 'Courier New', monospace;
            font-size: 32px;
            color: #dc3545;
            margin: 15px 0;
            font-weight: bold;
        }
        .preview-area {
            margin: 40px 0;
            min-height: 300px;
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 30px;
            background: #f8f9fa;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }
        .preview-video {
            max-width: 100%;
            border-radius: 10px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        .share-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin: 30px 0;
            display: none;
        }
        .share-section.active { display: block; }
        .submit-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 18px 40px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            margin: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102,126,234,0.3);
            text-decoration: none;
            display: inline-block;
        }
        .submit-btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102,126,234,0.4);
        }
        .submit-btn:disabled { 
            background: #6c757d; 
            cursor: not-allowed; 
            transform: none;
            box-shadow: none;
        }
        .status {
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
            font-weight: 500;
        }
        .status-info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .status-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .loading.active { display: block; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4285f4;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .google-drive-link {
            background: #e8f5e8;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #4285f4;
        }
        .google-drive-link h4 {
            color: #1a73e8;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .google-drive-link input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            font-family: monospace;
            background: white;
            border: 2px solid #4285f4;
            border-radius: 6px;
            font-size: 14px;
        }
        @media (max-width: 768px) {
            .container { padding: 20px; }
            .step-guide { grid-template-columns: 1fr; }
            .record-btn { min-width: auto; width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 Screen Recording Tool</h1>
            <p>Show us your issue by recording your screen</p>
            <p style="font-size: 1em; color: #888;">Blueshift Support - Help us help you faster</p>
        </div>

        <div class="step-guide">
            <div class="step">
                <div class="step-number">1</div>
                <h4>Click Record</h4>
                <p>Start screen recording and choose what to share</p>
            </div>
            <div class="step">
                <div class="step-number">2</div>
                <h4>Show the Issue</h4>
                <p>Demonstrate the problem while explaining what's wrong</p>
            </div>
            <div class="step">
                <div class="step-number">3</div>
                <h4>Get Google Drive Link</h4>
                <p>We'll upload to Google Drive and give you a shareable link</p>
            </div>
        </div>

        <div class="record-section">
            <button id="recordBtn" class="record-btn">🎬 Start Screen Recording</button>
            <button id="stopBtn" class="record-btn" disabled>⏹️ Stop Recording</button>
            
            <div class="recording-status" id="recordingStatus">
                <div class="timer" id="timer">00:00</div>
                🔴 RECORDING - Show us what's wrong!
            </div>
        </div>

        <div class="loading" id="loadingSection">
            <div class="spinner"></div>
            <p>Uploading your recording to Google Drive...</p>
        </div>

        <div class="preview-area" id="previewArea">
            <div>
                <h3 style="color: #666; margin: 0;">Your recording will appear here</h3>
                <p style="color: #888;">Click "Start Screen Recording" above to begin</p>
            </div>
        </div>

        <div class="share-section" id="shareSection">
            <h3>🔗 Your Recording is on Google Drive!</h3>
            <p>Your video has been uploaded to our secure Google Drive folder. Here's your shareable link:</p>
            
            <div class="google-drive-link">
                <h4>📄 Google Drive Link</h4>
                <input type="text" id="driveUrl" readonly>
                <button id="copyDriveBtn" class="submit-btn" style="background: #4285f4; width: 100%;">
                    📋 Copy Google Drive Link to Share with Agent
                </button>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0;">
                <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center;">
                    <h4 style="color: #1976d2; margin-top: 0;">💾 Download Backup</h4>
                    <p style="color: #666;">Keep a local copy on your computer.</p>
                    <a id="downloadBtn" href="#" class="submit-btn" style="background: #1976d2;">
                        📥 Download Video
                    </a>
                </div>
                
                <div style="background: #fff3e0; padding: 20px; border-radius: 10px; text-align: center;">
                    <h4 style="color: #ef6c00; margin-top: 0;">📞 Next Steps</h4>
                    <p style="color: #666;">Paste the Google Drive link in your support ticket or chat.</p>
                    <p style="font-size: 14px; color: #666;">✅ Agents can view directly</p>
                </div>
            </div>

            <button id="recordNewBtn" class="submit-btn" style="background: #6c757d; margin-top: 20px;" onclick="resetRecording()">
                🔄 Record Another Video
            </button>
        </div>

        <div id="status"></div>
    </div>

    <script>
        let mediaRecorder;
        let recordedChunks = [];
        let stream;
        let startTime;
        let timerInterval;

        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const previewArea = document.getElementById('previewArea');
        const shareSection = document.getElementById('shareSection');
        const loadingSection = document.getElementById('loadingSection');
        const status = document.getElementById('status');
        const recordingStatus = document.getElementById('recordingStatus');
        const timer = document.getElementById('timer');
        const driveUrl = document.getElementById('driveUrl');
        const copyDriveBtn = document.getElementById('copyDriveBtn');
        const downloadBtn = document.getElementById('downloadBtn');

        // Check browser compatibility
        if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
            showStatus('Screen recording requires Chrome, Firefox, or Edge. Please use one of these browsers.', 'error');
            recordBtn.disabled = true;
            recordBtn.textContent = '❌ Browser Not Supported';
        }

        recordBtn.addEventListener('click', startRecording);
        stopBtn.addEventListener('click', stopRecording);
        copyDriveBtn.addEventListener('click', copyDriveLink);

        async function startRecording() {
            try {
                stream = await navigator.mediaDevices.getDisplayMedia({
                    video: { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 30 } },
                    audio: { echoCancellation: false, autoGainControl: false, noiseSuppression: false }
                });

                recordedChunks = [];
                
                let mimeType = 'video/webm;codecs=vp9,opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'video/webm;codecs=vp8,opus';
                }
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'video/webm';
                }

                mediaRecorder = new MediaRecorder(stream, { mimeType });

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        recordedChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    const blob = new Blob(recordedChunks, { type: 'video/webm' });
                    
                    // Show loading
                    loadingSection.classList.add('active');
                    
                    // Create video preview
                    const video = document.createElement('video');
                    const localUrl = URL.createObjectURL(blob);
                    video.src = localUrl;
                    video.controls = true;
                    video.className = 'preview-video';
                    video.style.maxWidth = '100%';
                    video.style.height = 'auto';
                    
                    previewArea.innerHTML = '';
                    previewArea.appendChild(video);

                    // Setup local download
                    const filename = `blueshift-recording-${new Date().getTime()}.webm`;
                    downloadBtn.href = localUrl;
                    downloadBtn.download = filename;

                    // Upload to Google Drive
                    await uploadToGoogleDrive(blob, filename);
                };

                stream.getVideoTracks()[0].addEventListener('ended', () => {
                    stopRecording();
                });

                mediaRecorder.start(1000);
                
                recordBtn.disabled = true;
                stopBtn.disabled = false;
                recordBtn.textContent = '🎬 Recording...';
                recordBtn.classList.add('recording');
                recordingStatus.classList.add('active');

                startTime = Date.now();
                timerInterval = setInterval(updateTimer, 1000);

                showStatus('🎥 Recording started! Please share your screen and show us the issue.', 'info');

                setTimeout(() => {
                    if (mediaRecorder && mediaRecorder.state === 'recording') {
                        stopRecording();
                        showStatus('Recording automatically stopped after 15 minutes.', 'info');
                    }
                }, 900000);

            } catch (err) {
                console.error('Error starting recording:', err);
                showStatus('Unable to start recording. Please make sure you grant permission to share your screen and try again.', 'error');
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                stream.getTracks().forEach(track => track.stop());
                
                recordBtn.disabled = false;
                stopBtn.disabled = true;
                recordBtn.textContent = '🎬 Start Screen Recording';
                recordBtn.classList.remove('recording');
                recordingStatus.classList.remove('active');

                clearInterval(timerInterval);
            }
        }

        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            timer.textContent = `${minutes}:${seconds}`;
        }

        async function uploadToGoogleDrive(blob, filename) {
            try {
                const formData = new FormData();
                formData.append('recording', blob, filename);
                formData.append('duration', timer.textContent);

                const response = await fetch('/api/upload-recording', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                loadingSection.classList.remove('active');

                if (response.ok && result.drive_url) {
                    driveUrl.value = result.drive_url;
                    shareSection.classList.add('active');
                    showStatus('✅ Recording uploaded to Google Drive! Your shareable link is ready.', 'success');
                } else {
                    throw new Error(result.error || 'Upload failed');
                }
            } catch (error) {
                console.error('Upload error:', error);
                loadingSection.classList.remove('active');
                showStatus('❌ Google Drive upload failed. You can still download the recording and share it manually.', 'error');
                
                // Show download option only
                downloadBtn.style.display = 'block';
            }
        }

        function copyDriveLink() {
            driveUrl.select();
            driveUrl.setSelectionRange(0, 99999);
            
            try {
                navigator.clipboard.writeText(driveUrl.value).then(() => {
                    copyDriveBtn.textContent = '✅ Google Drive Link Copied!';
                    copyDriveBtn.style.background = '#34a853';
                    setTimeout(() => {
                        copyDriveBtn.textContent = '📋 Copy Google Drive Link to Share with Agent';
                        copyDriveBtn.style.background = '#4285f4';
                    }, 3000);
                });
            } catch (err) {
                document.execCommand('copy');
                showStatus('Google Drive link copied to clipboard!', 'success');
            }
        }

        function resetRecording() {
            shareSection.classList.remove('active');
            loadingSection.classList.remove('active');
            previewArea.innerHTML = `
                <div>
                    <h3 style="color: #666; margin: 0;">Ready for another recording</h3>
                    <p style="color: #888;">Click "Start Screen Recording" above to begin</p>
                </div>
            `;
            
            recordBtn.disabled = false;
            stopBtn.disabled = true;
            recordBtn.textContent = '🎬 Start Screen Recording';
            recordBtn.classList.remove('recording');
            
            recordedChunks = [];
            driveUrl.value = '';
            
            showStatus('Ready to record again!', 'info');
        }

        function showStatus(message, type) {
            status.innerHTML = `<div class="status status-${type}">${message}</div>`;
            
            if (type === 'info') {
                setTimeout(() => {
                    status.innerHTML = '';
                }, 8000);
            }
        }
    </script>
</body>
</html>
'''

ADMIN_LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - Screen Recording Tool</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; background: #f5f7fa; }
        .login-form { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #007cba; color: white; padding: 12px; width: 100%; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .error { color: #d73527; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="login-form">
        <h2>🔐 Admin Access</h2>
        <p>Screen Recording Tool Administration</p>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''

ADMIN_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard - Screen Recording Tool</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f7fa; }
        .header { background: #007cba; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; }
        .logout { float: right; background: rgba(255,255,255,0.2); color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; }
        .customer-link { background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; margin: 10px 0; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .google-drive-status { padding: 15px; border-radius: 8px; margin: 20px 0; }
        .drive-enabled { background: #e8f5e8; color: #1b5e20; border: 1px solid #c8e6c8; }
        .drive-disabled { background: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }
    </style>
</head>
<body>
    <div class="header">
        <a href="/admin/logout" class="logout">Logout</a>
        <h1>🛠️ Screen Recording Admin</h1>
        <p>Blueshift Support Tool Management</p>
    </div>
    
    <div class="container">
        <h2>📋 Customer Interface</h2>
        <p>Share this link with customers who need to record their screen:</p>
        <a href="/recording" target="_blank" class="customer-link">
            🎬 Customer Recording Interface
        </a>
        <p><strong>Public URL:</strong> <code>{{ request.url_root }}recording</code></p>
    </div>
    
    <div class="container">
        <h2>📁 Google Drive Status</h2>
        {% if google_drive_enabled %}
        <div class="google-drive-status drive-enabled">
            <strong>✅ Google Drive Connected</strong><br>
            Recordings are automatically uploaded to your Google Drive and customers get shareable links.
            {% if folder_configured %}
            <br>📁 Uploading to specific folder
            {% else %}
            <br>📁 Uploading to Drive root (consider setting GOOGLE_DRIVE_FOLDER_ID)
            {% endif %}
        </div>
        {% else %}
        <div class="google-drive-status drive-disabled">
            <strong>❌ Google Drive Not Configured</strong><br>
            Users can only download recordings locally. Configure Google Drive service account for shareable links.
        </div>
        {% endif %}
    </div>
    
    <div class="container">
        <h2>📊 System Status</h2>
        <div class="stats">
            <div class="stat-card">
                <h3>✅ System</h3>
                <p>Operational</p>
            </div>
            <div class="stat-card">
                <h3>🌐 Recording</h3>
                <p>Available</p>
            </div>
            <div class="stat-card">
                <h3>📁 Google Drive</h3>
                <p>{{ 'Connected' if google_drive_enabled else 'Not Setup' }}</p>
            </div>
            <div class="stat-card">
                <h3>🔒 Security</h3>
                <p>Protected</p>
            </div>
        </div>
    </div>
    
    <div class="container">
        <h2>ℹ️ How It Works</h2>
        <ol>
            <li>Customer visits the recording interface</li>
            <li>Records their screen showing the issue</li>
            {% if google_drive_enabled %}
            <li>Recording is automatically uploaded to Google Drive</li>
            <li>Customer gets a Google Drive shareable link</li>
            <li>Customer pastes the link in support ticket/chat</li>
            <li>Agents can click the link to view the video directly in browser</li>
            {% else %}
            <li>Downloads the video file to their computer</li>
            <li>Shares the recording file manually with support agents</li>
            {% endif %}
        </ol>
    </div>
</body>
</html>
'''

# Routes
@app.route('/')
def index():
    return redirect(url_for('recording'))

@app.route('/recording')
def recording():
    return render_template_string(CUSTOMER_INTERFACE)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template_string(ADMIN_LOGIN_TEMPLATE)
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    if verify_admin_password(username, password):
        session['authenticated'] = True
        session['username'] = username
        return redirect(url_for('admin_dashboard'))
    else:
        return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Invalid credentials")

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('recording'))

@app.route('/admin')
@require_auth
def admin_dashboard():
    # Check Google Drive configuration
    drive_enabled = bool(GOOGLE_CREDENTIALS_JSON and google_drive_available)
    folder_configured = bool(GOOGLE_DRIVE_FOLDER_ID)
    
    return render_template_string(
        ADMIN_DASHBOARD_TEMPLATE,
        google_drive_enabled=drive_enabled,
        folder_configured=folder_configured
    )

@app.route('/api/upload-recording', methods=['POST'])
def upload_recording():
    """Handle recording upload to Google Drive"""
    try:
        recording_file = request.files.get('recording')
        duration = request.form.get('duration', '00:00')
        
        if not recording_file:
            return jsonify({"error": "No recording file provided"}), 400
        
        # Generate unique filename
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        filename = f"blueshift-recording-{timestamp}-{unique_id}.webm"
        
        # Read file data
        file_data = recording_file.read()
        
        # Upload to Google Drive
        if not google_drive_available:
            return jsonify({"error": "Google Drive integration not available"}), 500
        
        drive_url, error_message = upload_to_google_drive(file_data, filename)
        
        if drive_url:
            # Log the recording
            recording_entry = {
                "id": unique_id,
                "filename": filename,
                "drive_url": drive_url,
                "duration": duration,
                "uploaded_at": datetime.now().isoformat(),
                "size_bytes": len(file_data)
            }
            
            recording_log.append(recording_entry)
            
            # Keep only last 100 recordings in memory
            if len(recording_log) > 100:
                recording_log.pop(0)
            
            return jsonify({
                "success": True,
                "drive_url": drive_url,
                "recording_id": unique_id,
                "message": "Recording uploaded to Google Drive successfully"
            })
        else:
            return jsonify({
                "error": f"Google Drive upload failed: {error_message or 'Unknown error'}",
                "fallback": True
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route('/health')
def health():
    # Check Google Drive status
    drive_status = "not_configured"
    if GOOGLE_CREDENTIALS_JSON and google_drive_available:
        drive_status = "configured"
    
    return jsonify({
        "status": "healthy",
        "app": "blueshiftsupport-screen-capture",
        "version": "2.0-googledrive",
        "recording_available": True,
        "google_drive": drive_status,
        "total_recordings": len(recording_log)
    })

@app.route('/api/info')
def api_info():
    return jsonify({
        "app_name": "Blueshift Support Screen Recording Tool",
        "version": "2.0.0-googledrive",
        "description": "Screen recording tool with Google Drive integration",
        "features": ["screen_recording", "google_drive_upload", "shareable_links", "admin_dashboard"],
        "storage": "Google Drive",
        "endpoints": {
            "customer_interface": "/recording",
            "admin_dashboard": "/admin",
            "upload_api": "/api/upload-recording",
            "health_check": "/health"
        }
    })

if __name__ == '__main__':
    print("🚀 Starting Blueshift Support Screen Recording Tool v2.0")
    print("📋 Customer interface: /recording")
    print("🛠️  Admin dashboard: /admin")
    
    if google_drive_available and GOOGLE_CREDENTIALS_JSON:
        print("📁 Google Drive: Ready for uploads")
        if GOOGLE_DRIVE_FOLDER_ID:
            print(f"📁 Upload folder: {GOOGLE_DRIVE_FOLDER_ID}")
    else:
        print("⚠️  Google Drive: Not configured (local download only)")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)