import React, { useEffect, useRef, useState } from 'react';
import './Profile.css';
import { API_BASE_URL } from '../../config';

function Profile({ user, onProfileUpdate }) {
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState('Loading profile...');
  const [error, setError] = useState('');
  const [profilePictureFile, setProfilePictureFile] = useState(null);
  const [profilePreviewUrl, setProfilePreviewUrl] = useState('');
  const [profileSaveBusy, setProfileSaveBusy] = useState(false);
  const [profileSaveStatus, setProfileSaveStatus] = useState('');
  const [profileSaveError, setProfileSaveError] = useState('');
  const [profileMetaName, setProfileMetaName] = useState('');
  const [profileMetaIdNo, setProfileMetaIdNo] = useState('');
  const [profileMetaBusy, setProfileMetaBusy] = useState(false);
  const [profileMetaStatus, setProfileMetaStatus] = useState('');
  const [profileMetaError, setProfileMetaError] = useState('');
  const [faceStatus, setFaceStatus] = useState('');
  const [faceError, setFaceError] = useState('');
  const [faceResult, setFaceResult] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [faceBusy, setFaceBusy] = useState(false);
  const [patternValue, setPatternValue] = useState('');
  const [patternVerifyValue, setPatternVerifyValue] = useState('');
  const [patternStatus, setPatternStatus] = useState('');
  const [patternError, setPatternError] = useState('');
  const [patternResult, setPatternResult] = useState(null);
  const [patternBusy, setPatternBusy] = useState(false);
  const videoRef = useRef(null);

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraOn(false);
  };

  useEffect(() => {
    let mounted = true;

    const fetchProfile = async () => {
      if (!user?.email) {
        setError('Missing user session.');
        setStatus('');
        return;
      }
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: user.email }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to load profile.');
        }
        if (!mounted) return;
        setProfile(data);
        setProfileMetaName(data?.name || '');
        setProfileMetaIdNo(data?.id_no || '');
        setStatus('');
        setError('');
      } catch (e) {
        if (!mounted) return;
        setError(String(e?.message || 'Failed to load profile.'));
        setStatus('');
      }
    };

    fetchProfile();
    return () => {
      mounted = false;
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  useEffect(() => {
    return () => {
      if (profilePreviewUrl) {
        URL.revokeObjectURL(profilePreviewUrl);
      }
    };
  }, [profilePreviewUrl]);

  const profileImage = profile?.profile_picture
    ? `${API_BASE_URL}/${String(profile.profile_picture).replace(/^\/+/, '')}`
    : '';
  const displayProfileImage = profilePreviewUrl || profileImage;
  const faceReferenceImage = profile?.face_reference_picture
    ? `${API_BASE_URL}/${String(profile.face_reference_picture).replace(/^\/+/, '')}`
    : '';

  const refreshProfile = async () => {
    if (!user?.email) return;
    const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.detail || 'Failed to refresh profile.');
    }
    setProfile(data);
    setProfileMetaName(data?.name || '');
    setProfileMetaIdNo(data?.id_no || '');
    // Sync profile picture to parent app for sidebar display
    if (typeof onProfileUpdate === 'function' && data?.profile_picture) {
      onProfileUpdate({
        profilePicture: data.profile_picture,
      });
    }
  };

  const handleSaveProfileMeta = async () => {
    if (!user?.email) {
      setProfileMetaError('Missing user session.');
      return;
    }
    if (!String(profileMetaName || '').trim()) {
      setProfileMetaError('Full Name is required.');
      return;
    }
    setProfileMetaBusy(true);
    setProfileMetaStatus('');
    setProfileMetaError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/profile/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: user.email,
          name: String(profileMetaName || '').trim(),
          id_no: String(profileMetaIdNo || '').trim(),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Failed to update profile.');
      }

      await refreshProfile();
      setProfileMetaStatus('Profile details updated.');
      if (typeof onProfileUpdate === 'function') {
        onProfileUpdate({
          name: data?.name || profileMetaName,
          idNo: data?.id_no || profileMetaIdNo,
          profilePicture: data?.profile_picture || profile?.profile_picture || '',
        });
      }
    } catch (e) {
      setProfileMetaError(String(e?.message || 'Failed to update profile.'));
    } finally {
      setProfileMetaBusy(false);
    }
  };

  const handleProfilePictureSelect = (e) => {
    const file = e.target.files?.[0] || null;
    setProfileSaveStatus('');
    setProfileSaveError('');
    setProfilePictureFile(file);
    if (profilePreviewUrl) {
      URL.revokeObjectURL(profilePreviewUrl);
    }
    if (file) {
      setProfilePreviewUrl(URL.createObjectURL(file));
    } else {
      setProfilePreviewUrl('');
    }
  };

  const handleSaveProfilePicture = async () => {
    if (!user?.email) {
      setProfileSaveError('Missing user session.');
      return;
    }
    if (!profilePictureFile) {
      setProfileSaveError('Select a profile picture first.');
      return;
    }

    setProfileSaveBusy(true);
    setProfileSaveStatus('');
    setProfileSaveError('');
    try {
      const formData = new FormData();
      formData.append('email', user.email);
      formData.append('name', String(profile?.name || user?.name || '').trim() || user.email.split('@')[0]);
      formData.append('id_no', String(profile?.id_no || user?.idNo || ''));
      formData.append('profile_picture', profilePictureFile);

      const response = await fetch(`${API_BASE_URL}/api/auth/profile/complete`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Failed to update profile picture.');
      }

      await refreshProfile();
      setProfilePictureFile(null);
      if (profilePreviewUrl) {
        URL.revokeObjectURL(profilePreviewUrl);
      }
      setProfilePreviewUrl('');
      setProfileSaveStatus('Profile picture updated.');

      if (typeof onProfileUpdate === 'function') {
        onProfileUpdate({
          name: data?.name || profile?.name || user?.name || '',
          idNo: data?.id_no || profile?.id_no || user?.idNo || '',
          profilePicture: data?.profile_picture || '',
        });
      }
    } catch (e) {
      setProfileSaveError(String(e?.message || 'Failed to update profile picture.'));
    } finally {
      setProfileSaveBusy(false);
    }
  };

  const startCamera = async () => {
    setFaceError('');
    setFaceResult(null);
    setFaceStatus('Accessing camera...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setCameraOn(true);
        setFaceStatus('Camera ready.');
      }
    } catch (e) {
      console.error('Camera error:', e);
      const errorMsg = e?.message || '';
      let msg = 'Failed to access camera. ';
      if (errorMsg.includes('Permission denied') || errorMsg.includes('NotAllowedError')) {
        msg += 'Please allow camera access in your browser settings. ';
        msg += 'Look for a camera icon in the address bar and click it to grant permission.';
      } else if (errorMsg.includes('NotFoundError') || errorMsg.includes('DevicesNotFoundError')) {
        msg += 'No camera found. Please connect a camera and try again.';
      } else if (errorMsg.includes('NotReadableError') || errorMsg.includes('TrackStartError')) {
        msg += 'Camera is in use by another app. Please close other apps using the camera.';
      } else {
        msg += 'Check that your camera is connected and you have granted permission.';
      }
      setFaceError(msg);
      setFaceStatus('');
    }
  };

  const captureFrameBlob = async () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) {
      throw new Error('Camera frame is not ready.');
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('Failed to capture frame.'));
          return;
        }
        resolve(blob);
      }, 'image/jpeg', 0.92);
    });
  };

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const handleRegisterFace = async () => {
    if (!cameraOn) {
      setFaceError('Start camera first.');
      return;
    }
    setFaceBusy(true);
    setFaceError('');
    setFaceResult(null);
    try {
      setFaceStatus('Capturing profile face...');
      const blob = await captureFrameBlob();
      const formData = new FormData();
      formData.append('email', user.email);
      formData.append('face_image', blob, 'face_reference.jpg');

      const response = await fetch(`${API_BASE_URL}/api/auth/profile/face/register`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Face registration failed.');
      }
      setFaceStatus('Face reference saved to profile.');
      await refreshProfile();
    } catch (e) {
      setFaceError(String(e?.message || 'Face registration failed.'));
      setFaceStatus('');
    } finally {
      setFaceBusy(false);
    }
  };

  const handleVerifyFace = async () => {
    if (!cameraOn) {
      setFaceError('Start camera first.');
      return;
    }
    setFaceBusy(true);
    setFaceError('');
    setFaceResult(null);
    try {
      setFaceStatus('Capture 1/3: Look at camera.');
      const f1 = await captureFrameBlob();
      await wait(800);
      setFaceStatus('Capture 2/3: Slightly turn your head.');
      const f2 = await captureFrameBlob();
      await wait(800);
      setFaceStatus('Capture 3/3: Return to center.');
      const f3 = await captureFrameBlob();

      const formData = new FormData();
      formData.append('email', user.email);
      formData.append('images', f1, 'frame_1.jpg');
      formData.append('images', f2, 'frame_2.jpg');
      formData.append('images', f3, 'frame_3.jpg');
      setFaceStatus('Running face verification...');

      const response = await fetch(`${API_BASE_URL}/api/auth/face/verify`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Face verification failed.');
      }
      const granted = Boolean(data?.matched && data?.liveness_passed && data?.num_faces === 1);
      setFaceResult({
        granted,
        distance: typeof data.distance === 'number' ? data.distance.toFixed(4) : 'N/A',
        message: granted ? 'Access granted' : 'Access denied',
      });
      setFaceStatus(granted ? 'Face verification passed.' : 'Face verification failed.');
    } catch (e) {
      setFaceError(String(e?.message || 'Face verification failed.'));
      setFaceStatus('');
    } finally {
      setFaceBusy(false);
    }
  };

  const handleRegisterPattern = async () => {
    setPatternBusy(true);
    setPatternError('');
    setPatternResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/profile/pattern/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, pattern: patternValue }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Pattern registration failed.');
      }
      setPatternStatus('Pattern registered.');
      await refreshProfile();
    } catch (e) {
      setPatternError(String(e?.message || 'Pattern registration failed.'));
      setPatternStatus('');
    } finally {
      setPatternBusy(false);
    }
  };

  const handleVerifyPattern = async () => {
    setPatternBusy(true);
    setPatternError('');
    setPatternResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/pattern/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, pattern: patternVerifyValue }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Pattern verification failed.');
      }
      const granted = Boolean(data?.access_granted);
      setPatternResult({
        granted,
        message: granted ? 'Access granted' : 'Access denied',
      });
      setPatternStatus(data?.message || (granted ? 'Pattern matched.' : 'Pattern mismatch.'));
    } catch (e) {
      setPatternError(String(e?.message || 'Pattern verification failed.'));
      setPatternStatus('');
    } finally {
      setPatternBusy(false);
    }
  };

  return (
    <div className="profile-page">
      <div className="page-header">
        <h1>Profile</h1>
        <p>Your account details</p>
      </div>

      {status && <div className="profile-status">{status}</div>}
      {error && <div className="profile-error">{error}</div>}

      {profile && (
        <>
          <div className="profile-card">
            <div className="profile-photo-wrap">
              {displayProfileImage ? (
                <img src={displayProfileImage} alt="Profile" className="profile-photo" />
              ) : (
                <div className="profile-photo-placeholder">NO PHOTO</div>
              )}
              <div className="profile-photo-edit">
                <label className="profile-btn secondary profile-file-btn" htmlFor="profile-picture-input">
                  Choose New Photo
                </label>
                <input
                  id="profile-picture-input"
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  onChange={handleProfilePictureSelect}
                  className="profile-file-input"
                />
                <button
                  type="button"
                  className="profile-btn"
                  disabled={!profilePictureFile || profileSaveBusy}
                  onClick={handleSaveProfilePicture}
                >
                  {profileSaveBusy ? 'Saving...' : 'Save Photo'}
                </button>
              </div>
              {profileSaveStatus && <div className="profile-status compact">{profileSaveStatus}</div>}
              {profileSaveError && <div className="profile-error compact">{profileSaveError}</div>}
            </div>

            <div className="profile-fields">
              <div className="profile-field">
                <span className="field-label">Full Name</span>
                <input
                  className="field-input"
                  type="text"
                  value={profileMetaName}
                  onChange={(e) => setProfileMetaName(e.target.value)}
                  placeholder="Enter full name"
                />
              </div>
              <div className="profile-field">
                <span className="field-label">Member ID</span>
                <input
                  className="field-input"
                  type="text"
                  value={profileMetaIdNo}
                  onChange={(e) => setProfileMetaIdNo(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="profile-fields-actions">
                <button type="button" className="profile-btn" disabled={profileMetaBusy} onClick={handleSaveProfileMeta}>
                  {profileMetaBusy ? 'Saving...' : 'Save Details'}
                </button>
              </div>
              {profileMetaStatus && <div className="profile-status compact">{profileMetaStatus}</div>}
              {profileMetaError && <div className="profile-error compact">{profileMetaError}</div>}
              <div className="profile-field">
                <span className="field-label">Email</span>
                <span className="field-value">{profile.email || '-'}</span>
              </div>
              <div className="profile-field">
                <span className="field-label">Profile Completed</span>
                <span className="field-value">{profile.profile_completed ? 'Yes' : 'No'}</span>
              </div>
              <div className="profile-field">
                <span className="field-label">Pattern Registered</span>
                <span className="field-value">{profile.pattern_registered ? 'Yes' : 'No'}</span>
              </div>
            </div>
          </div>

          <div className="profile-card profile-biometrics">
            <div className="profile-bio-column">
              <h3>Face Registration and Verification</h3>
              <p className="profile-help">Register a face in profile, then verify webcam match for access grant.</p>
              <div className="profile-video-wrap">
                <video ref={videoRef} autoPlay muted playsInline className="profile-video" />
                {!cameraOn && <div className="profile-video-placeholder">Camera Inactive</div>}
              </div>
              <div className="profile-actions">
                {!cameraOn ? (
                  <button type="button" className="profile-btn" onClick={startCamera}>Start Camera</button>
                ) : (
                  <button type="button" className="profile-btn secondary" onClick={stopCamera}>Stop Camera</button>
                )}
                <button type="button" className="profile-btn" disabled={!cameraOn || faceBusy} onClick={handleRegisterFace}>
                  {faceBusy ? 'Working...' : 'Register Face'}
                </button>
                <button type="button" className="profile-btn" disabled={!cameraOn || faceBusy} onClick={handleVerifyFace}>
                  {faceBusy ? 'Working...' : 'Verify Face'}
                </button>
              </div>
              {faceReferenceImage && (
                <div className="profile-face-ref">
                  <span className="field-label">Current Face Reference</span>
                  <img src={faceReferenceImage} alt="Face Reference" className="profile-face-ref-image" />
                </div>
              )}
              {faceStatus && <div className="profile-status">{faceStatus}</div>}
              {faceError && <div className="profile-error">{faceError}</div>}
              {faceResult && (
                <div className={`profile-access ${faceResult.granted ? 'allow' : 'deny'}`}>
                  {faceResult.message} | Distance: {faceResult.distance}
                </div>
              )}
            </div>

            <div className="profile-bio-column">
              <h3>Pattern Registration and Verification</h3>
              <p className="profile-help">Enter numeric pattern sequence, for example: 1-5-9-8-7.</p>
              <label className="profile-input-label" htmlFor="pattern-register-input">Register Pattern</label>
              <input
                id="pattern-register-input"
                className="profile-input"
                type="text"
                value={patternValue}
                onChange={(e) => setPatternValue(e.target.value)}
                placeholder="1-5-9-8-7"
              />
              <div className="profile-actions">
                <button
                  type="button"
                  className="profile-btn"
                  disabled={patternBusy || String(patternValue || '').trim().length === 0}
                  onClick={handleRegisterPattern}
                >
                  {patternBusy ? 'Working...' : 'Register Pattern'}
                </button>
              </div>

              <label className="profile-input-label" htmlFor="pattern-verify-input">Verify Pattern</label>
              <input
                id="pattern-verify-input"
                className="profile-input"
                type="text"
                value={patternVerifyValue}
                onChange={(e) => setPatternVerifyValue(e.target.value)}
                placeholder="Enter your pattern"
              />
              <div className="profile-actions">
                <button
                  type="button"
                  className="profile-btn"
                  disabled={patternBusy || String(patternVerifyValue || '').trim().length === 0}
                  onClick={handleVerifyPattern}
                >
                  {patternBusy ? 'Working...' : 'Verify Pattern'}
                </button>
              </div>

              {patternStatus && <div className="profile-status">{patternStatus}</div>}
              {patternError && <div className="profile-error">{patternError}</div>}
              {patternResult && (
                <div className={`profile-access ${patternResult.granted ? 'allow' : 'deny'}`}>
                  {patternResult.message}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Profile;
