const fs = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '..');
const mediaExtensions = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp3', '.wav', '.ogg', '.m4a']);

function mediaBytes(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).reduce((total, entry) => {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return total + mediaBytes(entryPath);
    if (!mediaExtensions.has(path.extname(entry.name).toLowerCase())) return total;
    return total + fs.statSync(entryPath).size;
  }, 0);
}

describe('Mini program package quality', () => {
  test('injects only required components', () => {
    const config = JSON.parse(fs.readFileSync(path.join(projectRoot, 'app.json'), 'utf8'));
    expect(config.lazyCodeLoading).toBe('requiredComponents');
    expect(config.requiredPrivateInfos).toEqual(['getLocation', 'chooseLocation']);
  });

  test('bundled images and audio stay below 200 KiB', () => {
    expect(mediaBytes(path.join(projectRoot, 'images'))).toBeLessThan(200 * 1024);
  });
});
