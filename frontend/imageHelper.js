/**
 * IMAGE PADDING DETECTOR
 * 
 * Your character images come in two types:
 *   1. NORMAL (tight crop) — e.g. idle pose: image fills nearly 100% of the PNG
 *   2. PADDED — e.g. mouth_open: 1024×1024 with ~35% black padding on each side,
 *               character only occupies the center 30% of image width
 *
 * The CSS in style.css handles both cases via the "padded-img" class:
 *   - padded images: scaled up 333% and shifted -35% to crop the black borders
 *   - normal images: displayed as-is
 *
 * USAGE IN YOUR MAIN JS:
 * --------------------------------------------------
 * import { detectPaddedImage, applyPaddingClass } from './imageHelper.js';
 *
 * // When loading a suspect image:
 * const img = document.querySelector('.suspect-img');
 * img.src = '/assets/characters/bald-uncle/mouth_open.png';
 * img.onload = () => applyPaddingClass(img);
 *
 * // Or use the inline helper when setting src:
 * setCharacterImage(suspectImg, '/assets/characters/bald-uncle/mouth_open.png');
 * --------------------------------------------------
 */

/**
 * Detects if an image has significant black/dark padding around the subject.
 * Uses a canvas to sample corner pixels and check if they're near-black.
 * 
 * @param {HTMLImageElement} img - A fully loaded <img> element
 * @param {number} threshold - Darkness threshold 0-255 (default: 15)
 * @returns {boolean} true if image has large dark padding
 */
export function detectPaddedImage(img, threshold = 15) {
  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);

    const w = img.naturalWidth;
    const h = img.naturalHeight;

    // Sample corners + left/right mid-edges to check for dark padding
    const samplePoints = [
      [0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1], // corners
      [0, Math.floor(h / 2)], [w - 1, Math.floor(h / 2)], // left/right middle
      [Math.floor(w * 0.15), Math.floor(h / 2)],  // 15% from left
      [Math.floor(w * 0.85), Math.floor(h / 2)],  // 15% from right
    ];

    let darkCount = 0;
    for (const [x, y] of samplePoints) {
      const pixel = ctx.getImageData(x, y, 1, 1).data;
      const brightness = (pixel[0] + pixel[1] + pixel[2]) / 3;
      if (brightness < threshold) darkCount++;
    }

    // If most sampled points are dark, it's a padded image
    return darkCount >= 5;
  } catch (e) {
    // CORS or other errors — assume not padded
    return false;
  }
}

/**
 * Applies or removes the "padded-img" CSS class based on image content.
 * Call this in the img.onload handler.
 * 
 * @param {HTMLImageElement} img
 */
export function applyPaddingClass(img) {
  if (detectPaddedImage(img)) {
    img.classList.add('padded-img');
  } else {
    img.classList.remove('padded-img');
  }
}

/**
 * Convenience: set an image src and auto-apply padding class on load.
 * 
 * @param {HTMLImageElement} img
 * @param {string} src
 */
export function setCharacterImage(img, src) {
  img.classList.remove('padded-img'); // reset while loading
  img.onload = () => applyPaddingClass(img);
  img.src = src;
}

/**
 * ALTERNATIVE: If you know which images are padded (mouth_open),
 * you can skip detection and just check the filename:
 *
 * export function isPaddedImage(src) {
 *   return src.includes('mouth_open') || src.includes('talking');
 * }
 *
 * Then in your code:
 * if (isPaddedImage(src)) img.classList.add('padded-img');
 */
