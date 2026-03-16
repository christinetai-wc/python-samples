/**
 * LINE API 共用模組
 * - 回覆訊息
 * - 主動推送
 * - 下載媒體
 */

function replyMessage(replyToken, text) {
  const url = 'https://api.line.me/v2/bot/message/reply';
  const payload = {
    replyToken: replyToken,
    messages: [{ type: 'text', text: text }]
  };
  UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    payload: JSON.stringify(payload)
  });
}

function pushMessage(targetId, text) {
  const url = 'https://api.line.me/v2/bot/message/push';
  const payload = {
    to: targetId,
    messages: [{ type: 'text', text: text }]
  };
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  const code = response.getResponseCode();
  if (code !== 200) {
    console.error('Push Message 失敗:', response.getContentText());
  }
  return code === 200;
}

function pushMessageWithMention(targetId, text, mentionUserId, mentionStart, mentionLength) {
  const url = 'https://api.line.me/v2/bot/message/push';
  const payload = {
    to: targetId,
    messages: [{
      type: 'text',
      text: text,
      mention: {
        mentionees: [{
          index: mentionStart,
          length: mentionLength,
          type: 'user',
          userId: mentionUserId
        }]
      }
    }]
  };
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  const code = response.getResponseCode();
  if (code !== 200) {
    console.error('Push Message with Mention 失敗:', response.getContentText());
  }
  return code === 200;
}

function downloadLineImage(messageId) {
  const url = `https://api-data.line.me/v2/bot/message/${messageId}/content`;
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN }
  });
  return response.getBlob();
}

// 測試
function testReplyAPI() {
  const url = 'https://api.line.me/v2/bot/info';
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: { 'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN },
    muteHttpExceptions: true
  });
  console.log('狀態碼:', response.getResponseCode());
  console.log('回應:', response.getContentText());
}
