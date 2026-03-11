import * as ImageManipulator from 'expo-image-manipulator';
import * as FileSystem from 'expo-file-system';

export interface CompressedImage {
  uri: string;
  base64: string;
  width: number;
  height: number;
  sizeKB: number;
}

export interface CompressionOptions {
  maxWidth?: number;
  maxHeight?: number;
  targetSizeKB?: number;
  quality?: number;
}

const DEFAULT_OPTIONS: CompressionOptions = {
  maxWidth: 800,
  maxHeight: 800,
  targetSizeKB: 100,
  quality: 0.7,
};

/**
 * Compress an image to target size (~100KB)
 * Uses iterative compression if needed
 */
export async function compressImage(
  uri: string,
  options: CompressionOptions = {}
): Promise<CompressedImage> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  
  let quality = opts.quality || 0.7;
  let result: ImageManipulator.ImageResult;
  let base64: string;
  let sizeKB: number;
  let attempts = 0;
  const maxAttempts = 5;

  // First pass - resize and compress
  result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: opts.maxWidth, height: opts.maxHeight } }],
    {
      compress: quality,
      format: ImageManipulator.SaveFormat.JPEG,
      base64: true,
    }
  );

  base64 = result.base64 || '';
  sizeKB = getBase64SizeKB(base64);

  // Iteratively reduce quality if still too large
  while (sizeKB > (opts.targetSizeKB || 100) && attempts < maxAttempts && quality > 0.3) {
    attempts++;
    quality -= 0.1;

    result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: opts.maxWidth, height: opts.maxHeight } }],
      {
        compress: quality,
        format: ImageManipulator.SaveFormat.JPEG,
        base64: true,
      }
    );

    base64 = result.base64 || '';
    sizeKB = getBase64SizeKB(base64);
  }

  // If still too large, reduce dimensions
  if (sizeKB > (opts.targetSizeKB || 100) * 2) {
    const smallerWidth = Math.round((opts.maxWidth || 800) * 0.7);
    const smallerHeight = Math.round((opts.maxHeight || 800) * 0.7);

    result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: smallerWidth, height: smallerHeight } }],
      {
        compress: 0.6,
        format: ImageManipulator.SaveFormat.JPEG,
        base64: true,
      }
    );

    base64 = result.base64 || '';
    sizeKB = getBase64SizeKB(base64);
  }

  return {
    uri: result.uri,
    base64: `data:image/jpeg;base64,${base64}`,
    width: result.width,
    height: result.height,
    sizeKB: Math.round(sizeKB),
  };
}

/**
 * Compress multiple images
 */
export async function compressImages(
  uris: string[],
  options: CompressionOptions = {},
  onProgress?: (current: number, total: number) => void
): Promise<CompressedImage[]> {
  const results: CompressedImage[] = [];
  
  for (let i = 0; i < uris.length; i++) {
    const compressed = await compressImage(uris[i], options);
    results.push(compressed);
    onProgress?.(i + 1, uris.length);
  }
  
  return results;
}

/**
 * Calculate base64 string size in KB
 */
function getBase64SizeKB(base64: string): number {
  // Base64 increases size by ~33%, so actual byte size is ~75% of string length
  const bytes = (base64.length * 3) / 4;
  return bytes / 1024;
}

/**
 * Validate image size (for server-side validation simulation)
 */
export function validateImageSize(base64: string, maxSizeKB: number = 500): boolean {
  const sizeKB = getBase64SizeKB(base64.replace(/^data:image\/\w+;base64,/, ''));
  return sizeKB <= maxSizeKB;
}

/**
 * Get human-readable file size
 */
export function formatFileSize(sizeKB: number): string {
  if (sizeKB < 1) {
    return `${Math.round(sizeKB * 1024)} B`;
  }
  if (sizeKB < 1024) {
    return `${Math.round(sizeKB)} KB`;
  }
  return `${(sizeKB / 1024).toFixed(1)} MB`;
}
