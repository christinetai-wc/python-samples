/**
 * LINE 傳檔存 Google Drive 模組
 * - 特定使用者私訊：文字設定目錄名稱，傳檔存到對應資料夾
 */

const SAVE2DRIVE_CONFIG = {
  ROOT_FOLDER_ID: '1FRXzD14YqThe7qLFqmjTkXe_0knc7I_0',
  SPREADSHEET_ID: '1Hc4GFBWG8qf6ZsPqal4j3Zqb0_PE5fXb9-r3RH2c2xA',
  // 允許使用此功能的 LINE User ID
  ALLOWED_USERS: {
    // 'Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx': '名稱',
  }
};

function isSave2DriveUser(userId) {
  return userId && SAVE2DRIVE_CONFIG.ALLOWED_USERS.hasOwnProperty(userId);
}

/**
 * 處理存檔訊息（從 Code.gs 分派過來）
 */
function handleSave2DriveMessage(event) {
  const cache = PropertiesService.getScriptProperties();
  const userId = event.source.userId;
  const replyToken = event.replyToken;

  // 文字 → 設定目錄名稱
  if (event.message.type === 'text') {
    const folderName = event.message.text.trim();
    cache.setProperty('s2d_' + userId, folderName);
    replyMessage(replyToken, '📁 已設定目錄：「' + folderName + '」，請傳送檔案。');
    return;
  }

  // 檔案（圖片、影片、音訊、文件）→ 存到 Google Drive
  const messageId = event.message.id;
  const msgType = event.message.type;
  const targetFolderName = cache.getProperty('s2d_' + userId) || '未分類檔案';

  let ext = '';
  if (msgType === 'image') ext = '.jpg';
  else if (msgType === 'video') ext = '.mov';
  else if (msgType === 'audio') ext = '.m4a';

  const fileName = event.message.fileName || (messageId + ext);

  try {
    const file = saveToDriveFolder(messageId, fileName, targetFolderName);
    if (file) {
      const fileUrl = file.getUrl();
      const sheet = SpreadsheetApp.openById(SAVE2DRIVE_CONFIG.SPREADSHEET_ID).getSheets()[0];
      sheet.appendRow([new Date(), targetFolderName, fileName, fileUrl]);
      replyMessage(replyToken, '✅ 存檔成功！\n連結：' + fileUrl);
    }
  } catch (err) {
    console.error('存檔失敗:', err);
    replyMessage(replyToken, '⚠️ 存檔失敗：' + err.message);
  }
}

function saveToDriveFolder(messageId, fileName, folderName) {
  const rootFolder = DriveApp.getFolderById(SAVE2DRIVE_CONFIG.ROOT_FOLDER_ID);
  const subFolders = rootFolder.getFoldersByName(folderName);
  let targetFolder;

  if (subFolders.hasNext()) {
    targetFolder = subFolders.next();
  } else {
    targetFolder = rootFolder.createFolder(folderName);
  }

  const url = 'https://api-data.line.me/v2/bot/message/' + messageId + '/content';
  const response = UrlFetchApp.fetch(url, {
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    method: 'get'
  });

  const blob = response.getBlob().setName(fileName);
  return targetFolder.createFile(blob);
}
