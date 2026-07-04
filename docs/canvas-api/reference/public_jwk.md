# Public JWK API

## Update Public JWK

### PUT /api/lti/developer_key/update_public_jwk

**Scope:** `url:PUT|/api/lti/developer_key/update_public_jwk`

Rotate the public key in jwk format when using lti services

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| public_jwk | Required | json | The new public jwk that will be set to the tools current public jwk. |

Returns a [DeveloperKey](developer_keys.html#DeveloperKey) object
