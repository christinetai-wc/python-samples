/**
 * LINE 傳檔存 Google Drive / YouTube 模組
 * - 特定使用者私訊：文字設定目錄名稱，傳檔存到對應資料夾
 * - 影片自動上傳到 YouTube（不公開），其他檔案存 Google Drive
 */

const SAVE2DRIVE_CONFIG = {
  ROOT_FOLDER_ID: '1FRXzD14YqThe7qLFqmjTkXe_0knc7I_0',
  SPREADSHEET_ID: '1Hc4GFBWG8qf6ZsPqal4j3Zqb0_PE5fXb9-r3RH2c2xA',
  YOUTUBE_CHANNEL_ID: 'UCItQEzzzPTW-AVJJGgAo1Bw',
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
    replyMessage(replyToken, '📁 已設定目錄：「' + folderName + '」，請傳送檔案。\n（影片會上傳到 YouTube，其他檔案存 Google Drive）');
    return;
  }

  const messageId = event.message.id;
  const msgType = event.message.type;
  const targetFolderName = cache.getProperty('s2d_' + userId) || '未分類檔案';

  // 影片 → YouTube
  if (msgType === 'video') {
    try {
      const videoUrl = uploadToYouTube(messageId, targetFolderName);
      if (videoUrl) {
        const sheet = SpreadsheetApp.openById(SAVE2DRIVE_CONFIG.SPREADSHEET_ID).getSheets()[0];
        sheet.appendRow([new Date(), targetFolderName, 'YouTube 影片', videoUrl]);
        replyMessage(replyToken, '✅ 影片已上傳到 YouTube！\n🎬 ' + videoUrl);
      }
    } catch (err) {
      console.error('YouTube 上傳失敗:', err);
      // YouTube 失敗時 fallback 到 Google Drive
      try {
        const file = saveToDriveFolder(messageId, messageId + '.mov', targetFolderName);
        if (file) {
          const sheet = SpreadsheetApp.openById(SAVE2DRIVE_CONFIG.SPREADSHEET_ID).getSheets()[0];
          sheet.appendRow([new Date(), targetFolderName, messageId + '.mov', file.getUrl()]);
          replyMessage(replyToken, '⚠️ YouTube 上傳失敗，已存到 Google Drive\n連結：' + file.getUrl());
        }
      } catch (err2) {
        replyMessage(replyToken, '⚠️ 存檔失敗：' + err.message);
      }
    }
    return;
  }

  // 其他檔案（圖片、音訊、文件）→ Google Drive
  let ext = '';
  if (msgType === 'image') ext = '.jpg';
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

/**
 * 上傳影片到 YouTube（不公開）
 */
function uploadToYouTube(messageId, title) {
  // 從 LINE 下載影片
  const url = 'https://api-data.line.me/v2/bot/message/' + messageId + '/content';
  const response = UrlFetchApp.fetch(url, {
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    method: 'get'
  });
  const blob = response.getBlob();

  // 產生標題（目錄名 + 日期時間）
  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  const videoTitle = title + ' ' + now;

  // 上傳到 YouTube
  const video = YouTube.Videos.insert(
    {
      snippet: {
        title: videoTitle,
        description: '由 LINE Bot 自動上傳\n' + now,
        categoryId: '27',  // Education
      },
      status: {
        privacyStatus: 'unlisted',  // 不公開（有連結才能看）
      }
    },
    'snippet,status',
    blob
  );

  return 'https://youtu.be/' + video.id;
}

/**
 * 存檔到 Google Drive
 */
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

/**
 * 測試 YouTube API 是否可用
 */
function testYouTubeAPI() {
  try {
    const channels = YouTube.Channels.list('snippet', { mine: true });
    console.log('YouTube 頻道數:', channels.items.length);
    for (const ch of channels.items) {
      console.log('  頻道:', ch.snippet.title, '/ ID:', ch.id);
    }
    console.log('✅ YouTube API 正常');
  } catch (e) {
    console.error('❌ YouTube API 錯誤:', e);
    console.log('請到 GAS 編輯器 → 服務 → 加入 YouTube Data API v3');
  }
}
