module.exports = function (config, env) {
  // Disable CSS minimizer in production
  if (env === 'production') {
    config.optimization.minimizer = [];
  }
  return config;
};
