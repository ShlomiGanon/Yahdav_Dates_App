const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const sharedRoot = path.resolve(projectRoot, '..', 'shared');

const config = getDefaultConfig(projectRoot);

// APP/shared lives outside this app's root, and Metro refuses to resolve
// or watch files outside projectRoot by default — babel-plugin-module-resolver
// rewriting '@shared/...' to a relative path isn't enough on its own.
config.watchFolders = [sharedRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
];

module.exports = config;
