const fs = require('fs');
const assert = require('assert');

function testPage(folderName, expectedLines) {
  const filePath = `music/${folderName}/index.html`;
  console.log(`\nTesting ${filePath}...`);
  const html = fs.readFileSync(filePath, 'utf-8');

  assert(html.includes('id="transModeGroup"'), 'transModeGroup missing in ' + folderName);
  assert(html.includes('data-mode="both"'), 'data-mode="both" missing in ' + folderName);
  assert(html.includes('data-mode="zh"'), 'data-mode="zh" missing in ' + folderName);
  assert(html.includes('data-mode="en"'), 'data-mode="en" missing in ' + folderName);
  assert(html.includes('.line-english'), '.line-english missing in ' + folderName);
  assert(html.includes('id="bgSeekBackwardBtn"'), 'bgSeekBackwardBtn missing in ' + folderName);
  assert(html.includes('id="bgSeekForwardBtn"'), 'bgSeekForwardBtn missing in ' + folderName);
  assert(html.includes('button.icon-btn.seek-btn'), 'seek-btn CSS missing in ' + folderName);
  assert(html.includes('bgAudio.currentTime = Math.max(0, bgAudio.currentTime - 5);'), 'seek backward handler missing in ' + folderName);
  assert(html.includes('bgSeekForwardBtn'), 'seek forward handler missing in ' + folderName);

  const startIdx = html.indexOf('const LYRICS_RAW = `');
  const endIdx = html.indexOf('`;', startIdx);
  const lyricsRaw = html.substring(startIdx + 'const LYRICS_RAW = `'.length, endIdx);

  const parseFnStart = html.indexOf('function parseLyrics(text) {');
  const parseFnEnd = html.indexOf('function render() {');
  const parseFnCode = html.substring(parseFnStart, parseFnEnd);

  const fn = new Function('text', parseFnCode + '\nreturn parseLyrics(text);');
  const sections = fn(lyricsRaw);

  let totalLines = 0, linesWithZh = 0, linesWithEn = 0;
  sections.forEach(sec => {
    sec.lines.forEach(ln => {
      totalLines++;
      if (ln.zh) linesWithZh++;
      if (ln.en) linesWithEn++;
    });
  });

  console.log(`[${folderName}] sections: ${sections.length}, total: ${totalLines}, zh: ${linesWithZh}, en: ${linesWithEn}`);
  assert.strictEqual(totalLines, expectedLines, `Total lines mismatch for ${folderName}`);
  assert.strictEqual(linesWithZh, expectedLines, `ZH lines mismatch for ${folderName}`);
  assert.strictEqual(linesWithEn, expectedLines, `EN lines mismatch for ${folderName}`);
  console.log(`[${folderName}] OK!`);
}

const target = process.argv[2];
if (target === 'music_1') testPage('music_1', 130);
else if (target === 'music_2') testPage('music_2', 117);
else if (target === 'music_3') testPage('music_3', 90);
else if (target === 'music_4') testPage('music_4', 96);
else {
  console.log('=== Running Full Suite for all 4 Music Pages ===');
  testPage('music_1', 130);
  testPage('music_2', 117);
  testPage('music_3', 90);
  testPage('music_4', 96);
  console.log('\n>>> ALL 4 MUSIC PAGES VERIFIED SUCCESSFULLY! <<<');
}
