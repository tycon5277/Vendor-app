// Client-side image compression targeting a KB budget while keeping quality reasonable.
// Mirrors the behavior of the old React Native app's compressImage helper.

export async function compressImage(file, {
  maxWidth = 800,
  maxHeight = 800,
  targetSizeKB = 100,
  minQuality = 0.4,
  startQuality = 0.8,
} = {}) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Could not load image'));
      image.src = url;
    });

    // Compute scale keeping aspect ratio
    const scale = Math.min(1, maxWidth / img.width, maxHeight / img.height);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // Try iteratively to hit the target size
    let quality = startQuality;
    let dataUrl = canvas.toDataURL('image/jpeg', quality);
    let sizeKB = Math.round((dataUrl.length * 3) / 4 / 1024);

    while (sizeKB > targetSizeKB && quality > minQuality) {
      quality = Math.max(minQuality, quality - 0.1);
      dataUrl = canvas.toDataURL('image/jpeg', quality);
      sizeKB = Math.round((dataUrl.length * 3) / 4 / 1024);
    }

    return {
      base64: dataUrl,
      uri: dataUrl,
      sizeKB,
      width: canvas.width,
      height: canvas.height,
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}
