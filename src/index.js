const fs = require("fs");
const { ipcRenderer } = require("electron");
let openedFilePath;
const codeElm = document.getElementById("code");

ipcRenderer.on("fileOpened", (event, { contents, filePath }) => {
    openedFilePath = filePath;
    document.getElementById('code').value = contents;
    document.getElementById("file-path").innerText = filePath;
})

ipcRenderer.on("saveFile" , (event) => {
    const currentCodeValue = codeElm.value;
    fs.writeFileSync(openedFilePath, currentCodeValue, "utf-8")
})