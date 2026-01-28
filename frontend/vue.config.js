const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  lintOnSave: false,
  productionSourceMap: false,
  configureWebpack: {
    devtool: false
  },
  devServer: {
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        // Don't proxy websockets; we only need HTTP for our Flask API
        ws: false,
        // Remove trailing slash mismatch issues
        pathRewrite: { '^/api': '/api' }
      }
    }
  }
})