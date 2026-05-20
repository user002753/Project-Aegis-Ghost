import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../config';
import './Gallery.css';

function Gallery() {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);
  const [filter, setFilter] = useState('all'); // all, ghost, stego, watermarked
  const [viewMode, setViewMode] = useState('grid'); // grid, list
  const [selectedImages, setSelectedImages] = useState([]);
  const [selectedBinImages, setSelectedBinImages] = useState([]);
  const [showBin, setShowBin] = useState(false);
  const [binImages, setBinImages] = useState([]);
  const [sortBy, setSortBy] = useState('name_asc'); // name_asc, name_desc, date_newest, date_oldest
  const [imageDates, setImageDates] = useState({});
  
  // Get user_id from sessionStorage
  const userId = sessionStorage.getItem('user_email') || sessionStorage.getItem('user_id') || 'anonymous';
  const binStorageKey = `aegis_bin_images_${userId.replace(/[^a-zA-Z0-9]/g, '_')}`;

  useEffect(() => {
    fetchImages();
    loadBinImages();
  }, [filter, sortBy]);

  const fetchImages = async () => {
    setLoading(true);
    try {
      // Pass user_id to get user-specific images
      const url = userId && userId !== 'anonymous' 
        ? `${API_BASE_URL}/api/outputs?user_id=${encodeURIComponent(userId)}`
        : `${API_BASE_URL}/api/outputs`;
      const response = await fetch(url);
      const data = await response.json();
      
      let filtered = data.files || [];
      
      // Apply filter
      if (filter === 'ghost') {
        filtered = filtered.filter(f => f.includes('ghost_') && f.endsWith('.png'));
      } else if (filter === 'stego') {
        filtered = filtered.filter(f => f.includes('stego_') && f.endsWith('.png'));
      } else if (filter === 'watermarked') {
        filtered = filtered.filter(f => f.includes('watermarked') && f.endsWith('.png'));
      }
      
      // Get dates for sorting
      const dates = {};
      filtered.forEach(f => {
        // Try to extract date from filename (format: adv_stego_1772213296_1.png or gemini_1772208904.png)
        const match = f.match(/(\d{10})/);
        if (match) {
          dates[f] = parseInt(match[1]) * 1000; // Convert to milliseconds
        } else {
          dates[f] = Date.now(); // Default to now if no date found
        }
      });
      setImageDates(dates);
      
      // Apply sorting
      if (sortBy === 'name_asc') {
        filtered.sort((a, b) => a.localeCompare(b));
      } else if (sortBy === 'name_desc') {
        filtered.sort((a, b) => b.localeCompare(a));
      } else if (sortBy === 'date_newest') {
        filtered.sort((a, b) => (dates[b] || 0) - (dates[a] || 0));
      } else if (sortBy === 'date_oldest') {
        filtered.sort((a, b) => (dates[a] || 0) - (dates[b] || 0));
      } else {
        filtered.sort();
      }
      
      setImages(filtered);
    } catch (error) {
      console.error('Error fetching images:', error);
    }
    setLoading(false);
  };

  const loadBinImages = () => {
    // Load bin images from localStorage (user-specific)
    const saved = localStorage.getItem(binStorageKey);
    if (saved) {
      setBinImages(JSON.parse(saved));
    }
  };

  const saveBinImages = (images) => {
    localStorage.setItem(binStorageKey, JSON.stringify(images));
    setBinImages(images);
  };

  const getImageUrl = (path) => {
    return `${API_BASE_URL}${path.replace('data', '/api/data')}`;
  };

  const handleDelete = (imagePath) => {
    if (window.confirm(`Move "${imagePath.split('/').pop()}" to bin?`)) {
      const newBin = [...binImages, imagePath];
      saveBinImages(newBin);
      setImages(images.filter(img => img !== imagePath));
    }
  };

  const handleRestore = (imagePath) => {
    const newBin = binImages.filter(img => img !== imagePath);
    saveBinImages(newBin);
    fetchImages();
  };

  const handlePermanentDelete = async (imagePath) => {
    if (window.confirm(`Permanently delete "${imagePath.split('/').pop()}"? This cannot be undone!`)) {
      try {
        // Call API to delete from server
        await fetch(`${API_BASE_URL}/api/outputs`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_paths: [imagePath], user_id: userId })
        });
      } catch (error) {
        console.error('Error deleting file:', error);
      }
      const newBin = binImages.filter(img => img !== imagePath);
      saveBinImages(newBin);
    }
  };

  const handleEmptyBin = () => {
    if (window.confirm('Empty bin? This will permanently delete all items.')) {
      saveBinImages([]);
    }
  };

  const toggleSelectImage = (imagePath) => {
    if (selectedImages.includes(imagePath)) {
      setSelectedImages(selectedImages.filter(img => img !== imagePath));
    } else {
      setSelectedImages([...selectedImages, imagePath]);
    }
  };

  const handleSelectAll = () => {
    if (selectedImages.length === images.length) {
      setSelectedImages([]);
    } else {
      setSelectedImages([...images]);
    }
  };

  // Bin selection functions
  const toggleBinSelectImage = (imagePath) => {
    if (selectedBinImages.includes(imagePath)) {
      setSelectedBinImages(selectedBinImages.filter(img => img !== imagePath));
    } else {
      setSelectedBinImages([...selectedBinImages, imagePath]);
    }
  };

  const handleDeleteSelectedBin = async () => {
    if (selectedBinImages.length === 0) return;
    if (!window.confirm(`Permanently delete ${selectedBinImages.length} selected item(s)? This cannot be undone!`)) {
      return;
    }
    
    try {
      // Call API to delete from server
      await fetch(`${API_BASE_URL}/api/outputs`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_paths: selectedBinImages, user_id: userId })
      });
    } catch (error) {
      console.error('Error deleting files:', error);
    }
    
    const newBin = binImages.filter(img => !selectedBinImages.includes(img));
    saveBinImages(newBin);
    setSelectedBinImages([]);
  };

  const handleDownloadZip = async () => {
    if (selectedImages.length === 0) {
      alert('Please select images to download');
      return;
    }

    try {
      // For now, download each image individually since we don't have ZIP library
      // In production, you'd use JSZip
      for (const img of selectedImages) {
        const url = getImageUrl(img);
        const link = document.createElement('a');
        link.href = url;
        link.download = img.split('/').pop();
        link.click();
      }
    } catch (error) {
      console.error('Error downloading:', error);
    }
  };

  const handleDownloadAll = async () => {
    // Download all visible images
    setSelectedImages([...images]);
    setTimeout(async () => {
      for (const img of images) {
        const url = getImageUrl(img);
        const link = document.createElement('a');
        link.href = url;
        link.download = img.split('/').pop();
        link.click();
        await new Promise(r => setTimeout(r, 300)); // Small delay between downloads
      }
    }, 100);
  };

  return (
    <div className="gallery-page">
      <div className="page-header">
        <h1>🖼️ Image Gallery</h1>
        <p>View, manage and download your generated images</p>
      </div>

      {/* Toolbar */}
      <div className="gallery-toolbar">
        <div className="filter-buttons">
          <button 
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => { setFilter('all'); setShowBin(false); }}
          >
            All
          </button>
          <button 
            className={`filter-btn ${filter === 'ghost' ? 'active' : ''}`}
            onClick={() => { setFilter('ghost'); setShowBin(false); }}
          >
            Ghost
          </button>
          <button 
            className={`filter-btn ${filter === 'stego' ? 'active' : ''}`}
            onClick={() => { setFilter('stego'); setShowBin(false); }}
          >
            Stego
          </button>
          <button 
            className={`filter-btn ${filter === 'watermarked' ? 'active' : ''}`}
            onClick={() => { setFilter('watermarked'); setShowBin(false); }}
          >
            Watermarked
          </button>
          <button 
            className={`filter-btn bin ${showBin ? 'active' : ''}`}
            onClick={() => setShowBin(true)}
          >
            🗑️ Bin ({binImages.length})
          </button>
        </div>

        {!showBin && (
          <div className="action-buttons">
            <select 
              className="sort-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="name_asc">Name (A-Z)</option>
              <option value="name_desc">Name (Z-A)</option>
              <option value="date_newest">Date (Newest)</option>
              <option value="date_oldest">Date (Oldest)</option>
            </select>
            <button className="action-btn" onClick={handleSelectAll}>
              {selectedImages.length === images.length ? '✓ Deselect All' : '✓ Select All'}
            </button>
            <button 
              className="action-btn download" 
              onClick={handleDownloadZip}
              disabled={selectedImages.length === 0}
            >
              ⬇️ Download Selected ({selectedImages.length})
            </button>
            <button className="action-btn" onClick={handleDownloadAll}>
              ⬇️ Download All
            </button>
          </div>
        )}
      </div>

      {/* Image Count */}
      <div className="gallery-info">
        {!showBin && (
          <span>{images.length} images • {selectedImages.length} selected</span>
        )}
      </div>

      {loading ? (
        <div className="loading">Loading images...</div>
      ) : (
        <>
          {showBin ? (
            // Bin View
            <div className="bin-toolbar">
              <span>{binImages.length} items • {selectedBinImages.length} selected</span>
              {selectedBinImages.length > 0 && (
                <button className="delete-selected-bin-btn" onClick={handleDeleteSelectedBin}>
                  🗑️ Delete Selected ({selectedBinImages.length})
                </button>
              )}
            </div>
          ) : null}
          {showBin ? (
            // Bin View
            <div className="gallery-grid">
              {binImages.length === 0 ? (
                <div className="empty-bin">🗑️ Bin is empty</div>
              ) : (
                <>
                  <button className="empty-bin-btn" onClick={handleEmptyBin}>
                    🗑️ Empty Bin
                  </button>
                  {binImages.map((imagePath, index) => (
                    <div 
                      key={index} 
                      className={`gallery-item bin-item ${selectedBinImages.includes(imagePath) ? 'selected' : ''}`}
                    >
                      <div 
                        className="select-checkbox"
                        onClick={(e) => { e.stopPropagation(); toggleBinSelectImage(imagePath); }}
                      >
                        {selectedBinImages.includes(imagePath) ? '✓' : ''}
                      </div>
                      <img 
                        src={getImageUrl(imagePath)} 
                        alt={`Bin ${index + 1}`}
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                      <div className="gallery-item-overlay">
                        <span>{imagePath.split('/').pop()}</span>
                        <div className="item-actions">
                          <button onClick={() => handleRestore(imagePath)}>♻️ Restore</button>
                          <button onClick={() => handlePermanentDelete(imagePath)}>❌ Delete</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          ) : (
            // Normal Gallery View
            <div className="gallery-grid">
              {images.map((imagePath, index) => (
                <div 
                  key={index} 
                  className={`gallery-item ${selectedImages.includes(imagePath) ? 'selected' : ''}`}
                >
                  <div 
                    className="select-checkbox"
                    onClick={(e) => { e.stopPropagation(); toggleSelectImage(imagePath); }}
                  >
                    {selectedImages.includes(imagePath) ? '✓' : ''}
                  </div>
                  <img 
                    src={getImageUrl(imagePath)} 
                    alt={`Image ${index + 1}`}
                    onClick={() => setSelectedImage(imagePath)}
                    onError={(e) => {
                      e.target.src = `${API_BASE_URL}/api/data/output_stego/ghost_${index + 1}.png`;
                    }}
                  />
                  <div className="gallery-item-overlay">
                    <span>{imagePath.split('/').pop()}</span>
                    <span className="image-date">
                      {imageDates[imagePath] ? new Date(imageDates[imagePath]).toLocaleString() : ''}
                    </span>
                    <div className="item-actions">
                      <a 
                        href={getImageUrl(imagePath)} 
                        download 
                        className="action-link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        ⬇️
                      </a>
                      <button 
                        onClick={(e) => { e.stopPropagation(); handleDelete(imagePath); }}
                        className="delete-btn"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Lightbox */}
      {selectedImage && (
        <div className="lightbox" onClick={() => setSelectedImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <img 
              src={getImageUrl(selectedImage)} 
              alt="Selected"
              onError={(e) => {
                const match = selectedImage.match(/ghost_(\d+)/);
                if (match) {
                  e.target.src = `${API_BASE_URL}/api/data/output_stego/ghost_${match[1]}.png`;
                }
              }}
            />
            <div className="lightbox-info">
              <span>{selectedImage.split('/').pop()}</span>
              <span className="image-date">
                {imageDates[selectedImage] ? new Date(imageDates[selectedImage]).toLocaleString() : ''}
              </span>
              <div className="lightbox-actions">
                <a 
                  href={getImageUrl(selectedImage)} 
                  download 
                  className="lightbox-btn"
                >
                  ⬇️ Download
                </a>
                <button 
                  className="lightbox-btn delete"
                  onClick={() => {
                    handleDelete(selectedImage);
                    setSelectedImage(null);
                  }}
                >
                  🗑️ Move to Bin
                </button>
              </div>
            </div>
            <button className="close-btn" onClick={() => setSelectedImage(null)}>×</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Gallery;
