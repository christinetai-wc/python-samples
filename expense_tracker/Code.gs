/**
 * LINE Bot 主程式 — 只負責設定、記錄群組 ID、分派任務
 *
 * 模組：
 *   LineApi.gs          — LINE API（reply / push / download）
 *   ExpenseTracker.gs   — 住院費用分帳 + 轉帳 + 收據
 *   MedicineReminder.gs — 吃藥提醒 + 排程
 *   FlashCard.gs         — FlashCard 家長群組（記錄 LINE User ID）
 *   Save2GoogleDrive.gs — 特定使用者傳檔存 Google Drive
 *   StudyRecorder.gs    — 自學群組（記錄到 Google Drive）
 *   Parser.gs           — 文字解析（記帳）
 *   SheetsManager.gs    — Google Sheets CRUD
 *   ImageHandler.gs     — 圖片上傳 + OCR
 */

// ===== 設定區 =====
const CONFIG = {
  LINE_CHANNEL_ACCESS_TOKEN: '43sBztOKS/p4UpvqODU3qEb8sbWSLss+NY1VoZ8yTkYVge34r7y6FkcxkbqN8hsu38/zKmxnJnL/a5V1ajOJZDQPp1UvGqiuvjeDwDmiOOZsi1ymBZfQTJND0m1Yor9xJaPas+wJq4QnTc5Ghbz54gdB04t89/1O/w1cDnyilFU=',
  LINE_CHANNEL_SECRET: 'fbfa8c82f3bcd40e53c3be6eb35e9e82',
  SPREADSHEET_ID: '18KE2dJHoyL6doRd2UEqb_4Xb6Er7Xvon9TSoQEDJw7w',
  GEMINI_API_KEY: 'AIzaSyDWjy43TkAuKY4qVqtxwEQRzt786ViMmmw',
  IMAGE_FOLDER_ID: '1Jeez9J0E5bbSrO2a4-VOI3kF4YG0BxS4'
};

// ===== Webhook 入口 =====

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ status: 'ok' }))
    .setMimeType(ContentService.MimeType.JSON);
}

function doOptions(e) {
  return ContentService.createTextOutput('')
    .setMimeType(ContentService.MimeType.TEXT);
}

/**
 * LINE Webhook — 記錄群組 ID → 依群組類型分派
 */
function doPost(e) {
  try {
    if (!e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const data = JSON.parse(e.postData.contents);
    if (!data.events || data.events.length === 0) {
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    for (const event of data.events) {
      const groupId = event.source && event.source.groupId;
      const userId = event.source && event.source.userId;

      // 1. 自動記錄群組 ID + 使用者 ID
      if (groupId) logGroupId(groupId);
      if (userId) logUserId(userId, groupId || '私訊');

      if (event.type !== 'message') continue;

      // 2. 群組訊息 → 依「群組清單」備註欄分派
      if (groupId) {
        const groupType = getGroupType(groupId);
        if (groupType === '自學')       { handleStudyMessage(event); }
        else if (groupType === 'FlashCard') { handleFlashCardMessage(event); }
        else if (groupType === '分帳')   { handleExpenseOrMedicineMessage(event); }
        // 未設定備註的群組 → 不處理
        continue;
      }

      // 3. 私訊 → 依使用者身分分派
      if (userId) {
        if (isExpenseUser(userId))       { handleExpenseOrMedicineMessage(event); }
        else if (isSave2DriveUser(userId)) { handleSave2DriveMessage(event); }
        // 不認識的人 → 不處理
      }
    }
  } catch (error) {
    console.error('Webhook 錯誤:', error);
  }

  return ContentService.createTextOutput(JSON.stringify({ status: 'ok' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ===== 測試函數 =====

function testWebhook() {
  console.log('Config:', CONFIG.SPREADSHEET_ID ? 'Sheets ID 已設定' : 'Sheets ID 未設定');
  console.log('LINE Token:', CONFIG.LINE_CHANNEL_ACCESS_TOKEN ? '已設定' : '未設定');
}

function testAuthorization() {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  console.log('Sheets 名稱:', ss.getName());
  const folders = DriveApp.getFoldersByName('ExpenseReceipts');
  console.log('Drive 存取正常');
  const props = PropertiesService.getScriptProperties();
  props.setProperty('test', 'ok');
  console.log('Properties 存取正常');
  const response = UrlFetchApp.fetch('https://www.google.com');
  console.log('UrlFetch 存取正常, 狀態碼:', response.getResponseCode());
  console.log('✅ 所有授權測試通過！');
}
