/**
 * 文字解析模組
 * - 解析記帳文字格式
 * - AI 輔助解析
 */

/**
 * 取得預設參與者（只包含參與均分的成員）
 */
function getDefaultParticipants() {
  const members = getAllMembers();
  if (members.length > 0) {
    // 只回傳參與均分的成員
    const participants = members.filter(m => m.joinSplit).map(m => m.name);
    return participants.length > 0 ? participants : ['我'];
  }
  return ['我'];  // 如果沒有成員，預設為「我」
}

/**
 * 解析記帳文字
 * @param {string} text - 輸入文字
 * @param {string} senderName - 發送者名稱
 * @returns {Object|null} { item, amount, payer, participants, splitType }
 */
function parseExpense(text, senderName) {
  text = text.trim();

  // 移除金額前的 $ 符號
  text = text.replace(/\$\s*/g, '');

  // 取得預設參與者（家庭名單）
  const defaultParticipants = getDefaultParticipants();

  // 情況1：只有「項目 金額」→ 預設均分（使用家庭名單）
  const patternSimple = /^(.+?)\s+(\d+(?:\.\d+)?)$/;
  const matchSimple = text.match(patternSimple);

  if (matchSimple) {
    return {
      item: matchSimple[1].trim(),
      amount: parseFloat(matchSimple[2]),
      payer: senderName,
      participants: defaultParticipants,
      splitType: '均分'
    };
  }

  // 情況2：「項目 金額 其他說明」
  const pattern = /^(.+?)\s+(\d+(?:\.\d+)?)\s+(.+)$/;
  const match = text.match(pattern);

  if (!match) {
    return null;
  }

  const item = match[1].trim();
  const amount = parseFloat(match[2]);
  const rest = match[3].trim();

  // 解析分攤方式和參與者
  const parts = rest.split(/\s+/);

  if (parts.length === 0) {
    return null;
  }

  const firstPart = parts[0];

  // 均分
  if (firstPart === '均分') {
    const participants = parts.length > 1 ? parts.slice(1) : defaultParticipants;

    return {
      item: item,
      amount: amount,
      payer: senderName,
      participants: participants,
      splitType: '均分'
    };
  }

  // 某人出/付（如：大哥出、二姐付）
  if (firstPart.endsWith('出') || firstPart.endsWith('付')) {
    const payer = firstPart.slice(0, -1);
    const participants = parts.length > 1 ? parts.slice(1) : defaultParticipants;

    return {
      item: item,
      amount: amount,
      payer: payer,
      participants: participants,
      splitType: '均分'
    };
  }

  // 「均分」黏在一起，如「350均分」
  if (firstPart.includes('均分')) {
    return {
      item: item,
      amount: amount,
      payer: senderName,
      participants: defaultParticipants,
      splitType: '均分'
    };
  }

  // 其他情況：把 rest 當作參與者名單，預設均分
  return {
    item: item,
    amount: amount,
    payer: senderName,
    participants: parts,
    splitType: '均分'
  };
}

/**
 * 使用 Gemini AI 解析文字
 * @param {string} text - 輸入文字
 * @param {string} senderName - 發送者名稱
 * @returns {Object|null}
 */
function parseWithAI(text, senderName) {
  const defaultParticipants = getDefaultParticipants();

  try {
    // 使用 gemini-2.5-flash-preview-09-2025 模型
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${CONFIG.GEMINI_API_KEY}`;

    const prompt = `你是一個記帳助手。請解析以下記帳文字，並用 JSON 格式回覆。

可能的成員名稱：${defaultParticipants.join('、')}
發送者是：${senderName}

輸入文字：${text}

請回覆 JSON 格式：
{
  "item": "項目名稱",
  "amount": 金額數字,
  "payer": "付款人",
  "participants": ["參與者1", "參與者2"],
  "splitType": "均分 或 指定"
}

規則：
- 如果沒有指定付款人，預設為發送者
- 如果沒有指定參與者，預設為所有成員
- 金額必須是數字
- 如果無法解析，回覆 {"error": true}`;

    const payload = {
      contents: [{
        parts: [{ text: prompt }]
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
    const result = JSON.parse(response.getContentText());

    if (result.candidates && result.candidates[0]) {
      const responseText = result.candidates[0].content.parts[0].text;

      // 提取 JSON
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[0]);

        if (!data.error && data.amount > 0) {
          return {
            item: data.item || '未命名',
            amount: Number(data.amount),
            payer: data.payer || senderName,
            participants: data.participants || defaultParticipants,
            splitType: data.splitType || '均分'
          };
        }
      }
    }

    return null;

  } catch (error) {
    console.error('AI 解析錯誤:', error);
    return null;
  }
}

/**
 * 測試解析函數
 */
function testParser() {
  // 先顯示家庭名單
  const members = getDefaultParticipants();
  console.log('預設參與者:', members.join(', '));
  console.log('---');

  const testCases = [
    '午餐 750',
    '午餐 350 均分',
    '午餐 350 均分 大哥 二姐 我',
    '掛號費 150 大哥出',
    '掛號費 150 大哥付',
    '看護費 2000 均分 大哥 二姐 我',
    '藥費 500.5 二姐出',
    '午餐 $600',
    '午餐 600 大哥 二姐 我'
  ];

  for (const text of testCases) {
    const result = parseExpense(text, '我');
    console.log(`輸入: ${text}`);
    console.log(`結果: ${JSON.stringify(result)}`);
    console.log('---');
  }
}
