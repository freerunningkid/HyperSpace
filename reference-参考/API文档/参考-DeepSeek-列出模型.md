# 列出模型

> 来源：DeepSeek API 官方文档

# 列出模型


```
GET https://api.deepseek.com/models
```


列出可用的模型列表，并提供相关模型的基本信息。请前往模型 & 价格查看当前支持的模型列表


## Responses​

- 200
OK, 返回模型列表

- application/json
- Schema
- Example (from schema)
- Example
Schema

object stringrequiredPossible values: [list]

data

Model[]

required

Array [

id stringrequired模型的标识符

object stringrequiredPossible values: [model]

对象的类型，其值为 model。

owned_by stringrequired拥有该模型的组织。

]

```
{  "object": "list",  "data": [    {      "id": "string",      "object": "model",      "owned_by": "string"    }  ]}
```

```
{  "object": "list",  "data": [    {      "id": "deepseek-v4-flash",      "object": "model",      "owned_by": "deepseek"    },    {      "id": "deepseek-v4-pro",      "object": "model",      "owned_by": "deepseek"    }  ]}
```

curlpythongonodejsrubycsharpphpjavapowershellCURL```bash
curl -L -X GET 'https://api.deepseek.com/models' \-H 'Accept: application/json' \-H 'Authorization: Bearer <TOKEN>'
```

Request Collapse allBase URLEdithttps://api.deepseek.comAuthBearer TokenSend API RequestResponseClearClick the Send API Request button above and see the response here!

上一页FIM 补全（Beta）下一页查询余额