module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [2, 'always', [
      'feat',
      'fix',
      'docs',
      'refactor',
      'perf',
      'chore',
      'test',
    ]],
    'body-leading-blank': [2, 'always', { ignoreEmpty: true }]
  }
};