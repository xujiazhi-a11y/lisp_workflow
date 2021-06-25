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
	backgroundColor: customTitlebar.Color.fromHex('#FFDE00'),
    // icon: "E:/electron_Dev/pythonElectron/icon/志语.svg",
});

function sendToPython() {
    let python = require('child_process').spawn('python', ['./py/hello.py', textarea.value]);
    python.stdout.on('data', function (data) {
      console.log("Python response: ", data.toString('utf8'));
    //   result.textContent = data.toString('utf8');
    });
  
    python.stderr.on('data', (data) => {
      console.error(`stderr: ${data}`);
    });
  
    python.on('close', (code) => {
      console.log(`child process exited with code ${code}`);
    });
  
  }

  btn.addEventListener('click', () => {
    sendToPython();
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