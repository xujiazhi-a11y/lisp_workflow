const fs = require("fs");
const { ipcRenderer } = require("electron");
let openedFilePath;
const textarea = document.getElementById("textarea");
const btn = document.getElementById("btn");
// customTitlebar
const customTitlebar = require('custom-electron-titlebar');

new customTitlebar.Titlebar({
    //menuPosition: 'left',
    // order: (title, menu),
    titleHorizontalAlignment: 'left',
	backgroundColor: customTitlebar.Color.fromHex('#1E1244'),
    // icon: "E:/electron_Dev/pythonElectron/icon/志语.svg",
});

const {PythonShell} = require('python-shell');

let options = {
    mode: 'text',
    pythonPath: 'C:\\Users\\ThinkPad\\AppData\\Local\\Programs\\Python\\Python38\\python.exe',
    pythonOptions: ['-u'], // get print results in real-time
    scriptPath: 'py',
    args: [textarea.value]
};

function sendToPythonShell() {
  PythonShell.run('Catkins_Dream.py', options, function (err, results) {
      if (err) throw err;
      // results is an array consisting of messages collected during execution
      console.log('results: %j', results);
  });
}

function sendToPython(filePath) {
    let python = require('child_process').spawn('python', ['./py/Catkins_Dream.py', filePath]);
    python.stdout.on('data', function (data) {
      console.log("Python response: ", data.toString('utf8'));
    //   result.textContent = data.toString('utf8');
    });
  
    python.stderr.on('data', (data) => {
      console.error(`stderr: ${data}`);
    });
  
    python.on('close', (code) => {
      console.log(`子进程退出编码： ${code}`);
    });
  
  }

btn.addEventListener('click', () => {
  console.log(openedFilePath)
  sendToPython(openedFilePath);
});
  
btn.dispatchEvent(new Event('click'));

ipcRenderer.on("fileOpened", (event, { contents, filePath }) => {
    openedFilePath = filePath;
    document.getElementById('textarea').value = contents;
    document.getElementById("file-path").innerText = filePath;
})

ipcRenderer.on("saveFile" , (event) => {
    const currentCodeValue = textarea.value;
    fs.writeFileSync(openedFilePath, currentCodeValue, "utf-8")
    sendToPython()
})