# Developer Key Account Bindings API

Developer key account bindings API for binding a developer key to a context and specifying a workflow state for that relationship.

### A DeveloperKeyAccountBinding object looks like:

``` example
{
  // The Canvas ID of the binding
  "id": 1,
  // The global Canvas ID of the account in the binding
  "account_id": 10000000000001,
  // The global Canvas ID of the developer key in the binding
  "developer_key_id": 10000000000008,
  // The workflow state of the binding. Will be one of 'on', 'off', or 'allow.'
  "workflow_state": on,
  // True if the requested context owns the binding
  "account_owns_binding": true
}
```

## Create a Developer Key Account Binding

### POST /api/v1/accounts/:account_id/developer_keys/:developer_key_id/developer_key_account_bindings

**Scope:** `url:POST|/api/v1/accounts/:account_id/developer_keys/:developer_key_id/developer_key_account_bindings`

Create a new Developer Key Account Binding. The developer key specified in the request URL must be available in the requested account or the requested account’s account chain. If the binding already exists for the specified account/key combination it will be updated.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| workflow_state |  | string | The workflow state for the binding. Must be one of “on”, “off”, or “allow”. Defaults to “off”. |

Returns a [DeveloperKeyAccountBinding](developer_key_account_bindings.html#DeveloperKeyAccountBinding) object
