var child_process = require('child_process');
var npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

var logger = {
  error: function (msg) {
    msg = msg || {};
    msg.flag = 0;
    console.log(JSON.stringify(msg));
  }
};

/*
  update: npm install new version
*/

try {
  require('fecoding');
} catch (e) {
  child_process.exec(npm + ' install fecoding', {
    cwd: __dirname
  }, function (error, stdout, stderr) {
    try {
      require('fecoding');
    } catch (e) {
      logger.error({
        msg: 'error: fecoding maybe not installed\ngoto: ' + __dirname + '\nrun "npm install fecoding"\n' + e.toString()
      });
    }
  });
}