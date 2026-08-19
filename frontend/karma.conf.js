// Karma configuration.
//
// Angular doesn't generate this file by default; it exists here to resolve
// the Chrome binary. In CI the GitHub runner ships with Chrome installed,
// but on a development machine it's typically only available inside
// Puppeteer's cache (for example, installed by another tool), and without
// this lookup `ng test` fails with "No binary for ChromeHeadless browser on
// your platform".

const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

/**
 * Checks that a Chrome binary actually launches.
 *
 * It's not enough that the file exists, nor to just pick the newest version:
 * an incomplete download or a broken cached version blows up on launch with
 * a stack dump that says nothing useful. A real headless launch is the only
 * reliable test, and it costs less than a second.
 */
function arranca(ruta) {
  try {
    execFileSync(ruta, ['--headless', '--no-sandbox', '--disable-gpu', '--dump-dom', 'about:blank'], {
      stdio: 'ignore',
      timeout: 30000,
    });
    return true;
  } catch {
    return false;
  }
}

/** Looks for a usable Chrome executable among the common locations. */
function localizarChrome() {
  if (process.env.CHROME_BIN && fs.existsSync(process.env.CHROME_BIN)) {
    return process.env.CHROME_BIN;
  }

  const candidatos = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ];

  const cachePuppeteer = path.join(os.homedir(), '.cache', 'puppeteer', 'chrome');
  if (fs.existsSync(cachePuppeteer)) {
    // The most recent available version is tried first.
    for (const version of fs.readdirSync(cachePuppeteer).sort().reverse()) {
      candidatos.push(path.join(cachePuppeteer, version, 'chrome-linux64', 'chrome'));
      candidatos.push(
        path.join(cachePuppeteer, version, 'chrome-mac-arm64', 'Google Chrome for Testing.app',
          'Contents', 'MacOS', 'Google Chrome for Testing'),
      );
    }
  }

  // Every candidate is tried until one actually launches, instead of
  // settling for the first one that exists.
  return candidatos.find((ruta) => fs.existsSync(ruta) && arranca(ruta));
}

const chrome = localizarChrome();
if (chrome) {
  process.env.CHROME_BIN = chrome;
}

module.exports = function (config) {
  config.set({
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('karma-jasmine-html-reporter'),
      require('karma-coverage'),
      require('@angular-devkit/build-angular/plugins/karma'),
    ],
    client: {
      jasmine: {},
      clearContext: false,
    },
    reporters: ['progress', 'kjhtml'],
    coverageReporter: {
      dir: path.join(__dirname, './coverage'),
      subdir: '.',
      reporters: [{ type: 'text-summary' }, { type: 'lcovonly' }, { type: 'html' }],
    },
    browsers: ['ChromeHeadlessSinSandbox'],
    customLaunchers: {
      // No sandbox because in CI containers the process runs without the
      // privileges Chrome needs to sandbox itself.
      ChromeHeadlessSinSandbox: {
        base: 'ChromeHeadless',
        flags: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
      },
    },
    restartOnFileChange: true,
  });
};
