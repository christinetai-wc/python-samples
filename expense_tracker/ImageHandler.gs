/**
 * 圖片處理模組
 * - 上傳圖片到 Google Drive
 * - OCR 辨識金額（使用 Gemini）
 */

/**
 * 上傳圖片到 Google Drive
 * @param {Blob} imageBlob - 圖片 Blob
 * @param {string} messageId - LINE 訊息 ID（作為檔名）
 * @returns {string} 圖片的公開連結
 */
function uploadImageToDrive(imageBlob, messageId) {
  try {
    // 取得或建立資料夾
    let folder;
    if (CONFIG.IMAGE_FOLDER_ID) {
      folder = DriveApp.getFolderById(CONFIG.IMAGE_FOLDER_ID);
    } else {
      // 沒有設定資料夾 ID，使用根目錄下的 ExpenseReceipts 資料夾
      const folders = DriveApp.getFoldersByName('ExpenseReceipts');
      if (folders.hasNext()) {
        folder = folders.next();
      } else {
        folder = DriveApp.createFolder('ExpenseReceipts');
      }
    }

    // 設定檔名
    const timestamp = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyyMMdd_HHmmss');
    const fileName = `receipt_${timestamp}_${messageId}.jpg`;

    // 建立檔案
    imageBlob.setName(fileName);
    const file = folder.createFile(imageBlob);

    // 設定為任何人可檢視
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

    // 回傳連結
    return file.getUrl();

  } catch (error) {
    console.error('上傳圖片錯誤:', error);
    return '';
  }
}

/**
 * 刪除 Google Drive 上的圖片
 * @param {string} url - 圖片 URL
 * @returns {boolean} 是否成功刪除
 */
function deleteImageFromDrive(url) {
  try {
    // 從 URL 提取檔案 ID
    // Google Drive URL 格式: https://drive.google.com/file/d/{fileId}/view
    const match = url.match(/\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) {
      console.log('無法從 URL 提取檔案 ID:', url);
      return false;
    }

    const fileId = match[1];
    const file = DriveApp.getFileById(fileId);
    file.setTrashed(true);

    console.log('已刪除圖片:', fileId);
    return true;

  } catch (error) {
    console.error('刪除圖片錯誤:', error);
    return false;
  }
}

/**
 * 使用 Gemini 辨識圖片金額
 * @param {Blob} imageBlob - 圖片 Blob
 * @returns {Object} { success: boolean, amount: number, items: string[] }
 */
function extractAmountFromImage(imageBlob) {
  try {
    // 將圖片轉為 base64
    const imageBytes = imageBlob.getBytes();
    const base64Image = Utilities.base64Encode(imageBytes);

    // 呼叫 Gemini API（使用 gemini-2.5-flash-preview-09-2025 模型）
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${CONFIG.GEMINI_API_KEY}`;

    const payload = {
      contents: [{
        parts: [
          {
            text: `這是一張收據或帳單的照片。請辨識：
1. 總金額（只要數字，不要貨幣符號）
2. 主要消費項目

請用以下 JSON 格式回覆：
{"amount": 數字, "items": ["項目1", "項目2"]}

如果無法辨識，回覆：{"amount": 0, "items": []}`
          },
          {
            inlineData: {
              mimeType: 'image/jpeg',
              data: base64Image
            }
          }
        ]
      }],
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 1024
      }
    };

    const options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    const response = UrlFetchApp.fetch(url, options);
    const responseText = response.getContentText();
    console.log('Gemini 回應:', responseText.substring(0, 500));  // 顯示前 500 字元

    const result = JSON.parse(responseText);

    if (result.error) {
      console.error('Gemini API 錯誤:', result.error.message);
      return { success: false, amount: 0, items: [] };
    }

    if (result.candidates && result.candidates[0] && result.candidates[0].content) {
      const text = result.candidates[0].content.parts[0].text;

      // 提取 JSON
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[0]);

        if (data.amount && data.amount > 0) {
          return {
            success: true,
            amount: Number(data.amount),
            items: data.items || []
          };
        }
      }
    }

    return { success: false, amount: 0, items: [] };

  } catch (error) {
    console.error('OCR 錯誤:', error);
    return { success: false, amount: 0, items: [] };
  }
}

/**
 * 測試 Gemini API 連線
 */
function testGeminiAPI() {
  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${CONFIG.GEMINI_API_KEY}`;

    const payload = {
      contents: [{
        parts: [{ text: '請回覆「OK」' }]
      }]
    };

    const options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    const response = UrlFetchApp.fetch(url, options);
    console.log('狀態碼:', response.getResponseCode());
    console.log('回應:', response.getContentText());

    if (response.getResponseCode() === 200) {
      console.log('✅ Gemini API 正常');
    } else {
      console.log('❌ Gemini API 錯誤');
    }

  } catch (error) {
    console.error('Gemini API 測試失敗:', error);
  }
}

/**
 * 測試圖片 OCR（從帳目紀錄抓圖片）
 */
function testOCR() {
  try {
    // 從帳目紀錄找一張有圖片連結的紀錄
    const expenses = getAllExpenses();
    let imageUrl = null;

    for (const exp of expenses) {
      const url = exp['圖片連結'];
      if (url && url.includes('drive.google.com')) {
        imageUrl = url;
        break;
      }
    }

    if (!imageUrl) {
      console.log('帳目紀錄中沒有圖片，請先用 LINE 傳一張收據圖片');
      return;
    }

    console.log('使用圖片:', imageUrl);

    // 從 URL 提取檔案 ID
    const match = imageUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) {
      console.log('無法解析圖片 URL');
      return;
    }

    const fileId = match[1];
    const file = DriveApp.getFileById(fileId);
    const imageBlob = file.getBlob();

    console.log('圖片大小:', imageBlob.getBytes().length, 'bytes');

    const result = extractAmountFromImage(imageBlob);
    console.log('OCR 結果:', JSON.stringify(result));

  } catch (error) {
    console.error('OCR 測試失敗:', error);
  }
}

/**
 * 使用 Google Drive 內建 OCR（備用方案）
 * @param {Blob} imageBlob - 圖片 Blob
 * @returns {string} OCR 文字
 */
function ocrWithDrive(imageBlob) {
  try {
    // 建立暫存檔案
    const tempFile = DriveApp.createFile(imageBlob);

    // 使用 Google Docs 開啟（會自動 OCR）
    const docFile = Drive.Files.copy(
      { title: 'temp_ocr', mimeType: MimeType.GOOGLE_DOCS },
      tempFile.getId(),
      { ocr: true }
    );

    // 讀取文字
    const doc = DocumentApp.openById(docFile.id);
    const text = doc.getBody().getText();

    // 刪除暫存檔案
    DriveApp.getFileById(docFile.id).setTrashed(true);
    tempFile.setTrashed(true);

    return text;

  } catch (error) {
    console.error('Drive OCR 錯誤:', error);
    return '';
  }
}
