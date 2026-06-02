# 图片生成 API 文档

本文档面向使用 `image2.mewinyou.shop` 通过 API 生成图片的用户。

## 基础信息

- Base URL：`https://image2.mewinyou.shop`
- 认证方式：所有接口都需要在请求头携带 Bearer Key。

```http
Authorization: Bearer YOUR_API_KEY
```

`YOUR_API_KEY` 可以是管理员密钥，也可以是在后台“用户密钥管理”里创建的用户密钥。用户密钥如果设置了图片额度，会按生成张数扣减；额度用完会返回 `429`。

## 通用错误格式

```json
{
  "detail": {
    "error": "错误信息"
  }
}
```

常见状态码：

- `400`：请求参数错误，例如缺少 `prompt`、`n` 超出范围、图片地址无效。
- `401`：密钥无效或已失效。
- `429`：没有可用账号额度，或用户密钥图片生成额度已用完。
- `502`：上游调用失败。

## 查询当前密钥信息

用于确认当前 Key 是否有效，以及查看用户密钥图片额度。

```http
GET /auth/me
```

### 示例

```bash
curl https://image2.mewinyou.shop/auth/me \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 响应

```json
{
  "ok": true,
  "version": "1.4.0",
  "role": "user",
  "subject_id": "abc123",
  "name": "普通用户",
  "image_quota": 100,
  "image_used": 12,
  "image_remaining": 88
}
```

字段说明：

- `image_quota`：图片生成上限；`0` 表示不限制。
- `image_used`：已使用张数。
- `image_remaining`：剩余张数；不限额时为 `null`。

## 查询可用模型

```http
GET /v1/models
```

### 示例

```bash
curl https://image2.mewinyou.shop/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 同步文生图

OpenAI 兼容接口，适合直接等待图片结果的场景。

```http
POST /v1/images/generations
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `prompt` | string | 是 | - | 图片描述词。 |
| `model` | string | 否 | `gpt-image-2` | 图片模型，例如 `gpt-image-2`、`codex-gpt-image-2`、`auto`。 |
| `n` | integer | 否 | `1` | 生成张数，范围 `1-4`。会按张数扣用户 key 额度。 |
| `size` | string/null | 否 | `null` | 图片尺寸，例如 `1024x1024`；为空时使用默认尺寸。 |
| `quality` | string | 否 | `auto` | 图片质量，通常使用 `auto`。 |
| `response_format` | string | 否 | `b64_json` | 返回格式，支持 `b64_json` 或 `url`。 |
| `stream` | boolean/null | 否 | `null` | 是否流式；普通 API 用户建议不传。 |

### 示例：返回 base64

```bash
curl https://image2.mewinyou.shop/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只穿宇航服的橘猫站在月球上，电影感，高清",
    "n": 1,
    "size": "1024x1024",
    "quality": "auto",
    "response_format": "b64_json"
  }'
```

### 示例：返回 URL

```bash
curl https://image2.mewinyou.shop/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "极简风格的咖啡店海报，米色背景",
    "response_format": "url"
  }'
```

### 响应

```json
{
  "created": 1710000000,
  "data": [
    {
      "b64_json": "iVBORw0KGgo...",
      "revised_prompt": "..."
    }
  ]
}
```

如果 `response_format` 为 `url`，则返回：

```json
{
  "created": 1710000000,
  "data": [
    {
      "url": "https://image2.mewinyou.shop/images/...png",
      "revised_prompt": "..."
    }
  ]
}
```

## 同步图生图 / 图片编辑

支持两种提交方式：`multipart/form-data` 上传本地图片，或 `application/json` 传图片 URL / base64。

```http
POST /v1/images/edits
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `prompt` | string | 是 | - | 编辑说明。 |
| `image` / `images` / `image_url` | file/string/array | 是 | - | 参考图。支持上传文件、图片 URL、data URL、base64。 |
| `model` | string | 否 | `gpt-image-2` | 图片模型。 |
| `n` | integer | 否 | `1` | 生成张数，范围 `1-4`。 |
| `size` | string/null | 否 | `null` | 图片尺寸。 |
| `quality` | string | 否 | `auto` | 图片质量。 |
| `response_format` | string | 否 | `b64_json` | `b64_json` 或 `url`。 |

### 示例：上传本地图片

```bash
curl https://image2.mewinyou.shop/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "image=@/path/to/input.png" \
  -F "prompt=把这张图改成赛博朋克风格，保留主体构图" \
  -F "model=gpt-image-2" \
  -F "n=1" \
  -F "response_format=url"
```

### 示例：使用图片 URL

```bash
curl https://image2.mewinyou.shop/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "把图片改成水彩插画风格",
    "image_url": "https://example.com/input.png",
    "response_format": "url"
  }'
```

### 示例：多张参考图

```bash
curl https://image2.mewinyou.shop/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "image=@/path/to/person.png" \
  -F "image=@/path/to/background.png" \
  -F "prompt=把人物自然合成到背景里，保持真实摄影风格" \
  -F "response_format=url"
```

## 异步文生图任务

适合前端轮询或不想长时间保持 HTTP 连接的场景。

```http
POST /api/image-tasks/generations
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `client_task_id` | string | 是 | - | 客户端生成的唯一任务 ID。重复提交同一 ID 会返回已有任务。 |
| `prompt` | string | 是 | - | 图片描述词。 |
| `model` | string | 否 | `gpt-image-2` | 图片模型。 |
| `size` | string/null | 否 | `null` | 图片尺寸。 |
| `quality` | string | 否 | `auto` | 图片质量。 |

### 创建任务

```bash
curl https://image2.mewinyou.shop/api/image-tasks/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client_task_id": "task-001",
    "prompt": "未来城市夜景，霓虹灯，超广角",
    "model": "gpt-image-2",
    "quality": "auto"
  }'
```

### 响应

```json
{
  "id": "task-001",
  "status": "queued",
  "mode": "generate",
  "model": "gpt-image-2",
  "size": "",
  "quality": "auto",
  "created_at": "2026-06-03 00:00:00",
  "updated_at": "2026-06-03 00:00:00"
}
```

## 异步图生图任务

```http
POST /api/image-tasks/edits
```

### 示例

```bash
curl https://image2.mewinyou.shop/api/image-tasks/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "client_task_id=edit-task-001" \
  -F "image=@/path/to/input.png" \
  -F "prompt=把图片改成宫崎骏动画风格" \
  -F "model=gpt-image-2"
```

## 查询异步任务结果

```http
GET /api/image-tasks?ids=task-001,task-002
```

如果不传 `ids`，返回当前 key 的任务列表。

### 示例

```bash
curl "https://image2.mewinyou.shop/api/image-tasks?ids=task-001" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 成功响应

```json
{
  "items": [
    {
      "id": "task-001",
      "status": "success",
      "mode": "generate",
      "model": "gpt-image-2",
      "quality": "auto",
      "created_at": "2026-06-03 00:00:00",
      "updated_at": "2026-06-03 00:00:30",
      "data": [
        {
          "url": "https://image2.mewinyou.shop/images/...png",
          "revised_prompt": "..."
        }
      ]
    }
  ],
  "missing_ids": []
}
```

### 任务状态

- `queued`：排队中。
- `running`：生成中。
- `success`：成功，读取 `data`。
- `error`：失败，读取 `error`。

## Python 示例

```python
import base64
import requests

BASE_URL = "https://image2.mewinyou.shop"
API_KEY = "YOUR_API_KEY"

resp = requests.post(
    f"{BASE_URL}/v1/images/generations",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "prompt": "一张高级感香水产品海报，黑金配色，商业摄影",
        "model": "gpt-image-2",
        "n": 1,
        "response_format": "b64_json",
    },
    timeout=180,
)
resp.raise_for_status()
image_b64 = resp.json()["data"][0]["b64_json"]
with open("output.png", "wb") as f:
    f.write(base64.b64decode(image_b64))
```

## JavaScript 示例

```js
const baseUrl = "https://image2.mewinyou.shop";
const apiKey = "YOUR_API_KEY";

const res = await fetch(`${baseUrl}/v1/images/generations`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    prompt: "一张高级感香水产品海报，黑金配色，商业摄影",
    model: "gpt-image-2",
    n: 1,
    response_format: "url",
  }),
});

if (!res.ok) {
  throw new Error(await res.text());
}

const data = await res.json();
console.log(data.data[0].url);
```

## 用户 key 图片额度说明

- 管理员可在后台为用户 key 设置 `图片生成上限`。
- `0` 表示不限额。
- 同步文生图会按 `n` 扣减额度。
- 同步图生图会按 `n` 扣减额度。
- 异步图片任务每个任务扣减 1 张额度。
- 如果生成失败，系统会退回已预扣额度。
- 额度不足时返回：

```json
{
  "detail": {
    "error": "图片生成额度已用完（已用 10/10）"
  }
}
```
