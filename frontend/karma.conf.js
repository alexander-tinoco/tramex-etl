// Configuracion de Karma.
//
// Angular no genera este archivo por defecto; existe aqui para resolver el
// binario de Chrome. En CI el runner de GitHub trae Chrome instalado, pero en
// una maquina de desarrollo lo habitual es tenerlo solo dentro de la cache de
// Puppeteer (por ejemplo, instalado por otra herramienta), y sin esta busqueda
// `ng test` falla con "No binary for ChromeHeadless browser on your platform".

const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

/**
 * Comprueba que un binario de Chrome arranca de verdad.
 *
 * No basta con que el archivo exista ni con quedarse con la versión más nueva:
 * una descarga incompleta o una versión rota en la caché revienta al arrancar
 * con un volcado de pila que no dice nada útil. Un arranque real en modo
 * headless es la única prueba fiable, y cuesta menos de un segundo.
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

/** Busca un ejecutable de Chrome utilizable entre las ubicaciones habituales. */
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
    // Se toma la version mas reciente disponible.
    for (const version of fs.readdirSync(cachePuppeteer).sort().reverse()) {
      candidatos.push(path.join(cachePuppeteer, version, 'chrome-linux64', 'chrome'));
      candidatos.push(
        path.join(cachePuppeteer, version, 'chrome-mac-arm64', 'Google Chrome for Testing.app',
          'Contents', 'MacOS', 'Google Chrome for Testing'),
      );
    }
  }

  // Se prueba cada candidato hasta encontrar uno que arranque, en lugar de
  // quedarse con el primero que exista.
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
      // Sin sandbox porque en contenedores de CI el proceso corre sin los
      // privilegios que Chrome necesita para aislarse.
      ChromeHeadlessSinSandbox: {
        base: 'ChromeHeadless',
        flags: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
      },
    },
    restartOnFileChange: true,
  });
};
