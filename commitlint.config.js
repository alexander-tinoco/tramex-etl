export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [
      2,
      'always',
      ['etl', 'backend', 'frontend', 'db', 'api', 'auth', 'security', 'infra', 'docker', 'ci', 'docs', 'deps', 'release', '']
    ],
    'header-max-length': [2, 'always', 120]
  }
};
