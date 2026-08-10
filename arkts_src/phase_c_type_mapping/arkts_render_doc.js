#!/usr/bin/env node
'use strict';

const { chromium } = require('/mnt/zengjy69/AlphaTrans/arkts_tools/playwright/node_modules/playwright');

async function main() {
  const url = process.argv[2];
  if (!url) throw new Error('URL is required');
  const query = process.argv[3] || '';
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage();
  try {
    await page.goto(url, {waitUntil: 'domcontentloaded', timeout: 30000});
    await page.waitForTimeout(4000);
    const result = await page.evaluate((searchText) => {
      const fullText = document.body ? document.body.innerText : '';
      const lines = fullText.split(/\n+/).map((line) => line.trim()).filter(Boolean);
      const marker = lines.findIndex((line) => line.includes('找到全部相关内容'));
      const resultText = marker >= 0 ? lines.slice(marker).join('\n') : '';
      return {
        url: window.location.href,
        text: fullText,
        resultText,
        query: searchText,
        links: Array.from(document.querySelectorAll('a[href]')).map((a) => ({
          text: (a.innerText || a.textContent || '').trim(),
          href: a.href,
        })),
      };
    }, query);
    process.stdout.write(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(String(error.stack || error));
  process.exit(1);
});
