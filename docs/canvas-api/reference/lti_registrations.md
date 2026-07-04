# LTI Registrations API

### BETA: This API resource is not finalized, and there could be breaking changes before its final release.

API for accessing and configuring LTI registrations in a root account. LTI Registrations can be any of:

- 1.3 Dynamic Registration
- 1.3 manual installation (via JSON, URL, or UI)
- 1.1 manual installation (via XML, URL, or UI)

The Dynamic Registration process uses a different API endpoint to finalize the process and create the registration. The [Registration guide](/doc/api/registration.html) has more details on that process.

### A Lti::Registration object looks like:

``` example
// A registration of an LTI tool in Canvas
{
  // the Canvas ID of the Lti::Registration object
  "id": 2,
  // Tool-provided registration name
  "name": "My LTI Tool",
  // Admin-configured friendly display name
  "admin_nickname": "My LTI Tool (Campus A)",
  // Tool-provided URL to the tool's icon
  "icon_url": "https://mytool.com/icon.png",
  // Tool-provided name of the tool vendor
  "vendor": "My Tool LLC",
  // The Canvas id of the account that owns this registration
  "account_id": 1,
  // Flag indicating if registration is internally-owned
  "internal_service": false,
  // Flag indicating if registration is owned by this account, or inherited from
  // Site Admin
  "inherited": false,
  // LTI version of the registration, either 1.1 or 1.3
  "lti_version": "1.3",
  // Flag indicating if registration was created using LTI Dynamic Registration.
  // Only present if lti_version is 1.3
  "dynamic_registration": false,
  // The state of the registration
  "workflow_state": "active",
  // Timestamp of the registration's creation
  "created_at": "2024-01-01T00:00:00Z",
  // Timestamp of the registration's last update
  "updated_at": "2024-01-01T00:00:00Z",
  // The user that created this registration. Not always present. If a string,
  // this registration was created by Instructure.
  "created_by": {"type":"User"},
  // The user that last updated this registration. Not always present. If a
  // string, this registration was last updated by Instructure.
  "updated_by": {"type":"User"},
  // The Canvas id of the root account
  "root_account_id": 1,
  // The binding for this registration and this account
  "account_binding": {"type":"Lti::RegistrationAccountBinding"},
  // The Canvas-style tool configuration for this registration
  "configuration": {"type":"Lti::ToolConfiguration"}
}
```

### A Lti::LegacyConfiguration object looks like:

``` example
// A legacy configuration format for LTI 1.3 tools.
{
  // The display name of the tool
  "title": "My Tool",
  // The description of the tool
  "description": "My Tool is built by me, for me.",
  // A key-value listing of all custom fields the tool has requested
  "custom_fields": {"context_title":"$Context.title","special_tool_thing":"foo1234"},
  // The default launch URL for the tool. Overridable by placements.
  "target_link_uri": "https://mytool.com/launch",
  // 1.3 specific. URL used for initial login request
  "oidc_initiation_url": "https://mytool.com/1_3/login",
  // 1.3 specific. Region-specific login URLs for data protection compliance
  "oidc_initiation_urls": {"eu-west-1":"https:\/\/dub.mytool.com\/1_3\/login"},
  // 1.3 specific. The tool's public JWK in JSON format. Discouraged in favor of a
  // url hosting a JWK set.
  "public_jwk": {"e":"AQAB","etc":"etc"},
  // 1.3 specific. The tool-hosted URL containing its public JWK keyset. Canvas
  // may cache JWKs up to 5 minutes.
  "public_jwk_url": "https://mytool.com/1_3/jwks",
  // 1.3 specific. List of LTI scopes requested by the tool
  "scopes": ["https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"],
  // Array of extensions for the tool
  "extensions": null
}
```

### A Lti::ToolConfiguration object looks like:

``` example
// A Registration's Canvas-specific tool configuration.
{
  // The display name of the tool
  "title": "My Tool",
  // The description of the tool
  "description": "My Tool is built by me, for me.",
  // A key-value listing of all custom fields the tool has requested
  "custom_fields": {"context_title":"$Context.title","special_tool_thing":"foo1234"},
  // The default launch URL for the tool. Overridable by placements.
  "target_link_uri": "https://mytool.com/launch",
  // The tool's main domain. Highly recommended for deep linking, used to match
  // links to the tool.
  "domain": "mytool.com",
  // Tool-provided identifier, can be anything
  "tool_id": "MyTool",
  // Canvas-defined privacy level for the tool
  "privacy_level": "public",
  // 1.3 specific. URL used for initial login request
  "oidc_initiation_url": "https://mytool.com/1_3/login",
  // 1.3 specific. Region-specific login URLs for data protection compliance
  "oidc_initiation_urls": {"eu-west-1":"https:\/\/dub.mytool.com\/1_3\/login"},
  // 1.3 specific. The tool's public JWK in JSON format. Discouraged in favor of a
  // url hosting a JWK set.
  "public_jwk": {"e":"AQAB","etc":"etc"},
  // 1.3 specific. The tool-hosted URL containing its public JWK keyset. Canvas
  // may cache JWKs up to 5 minutes.
  "public_jwk_url": "https://mytool.com/1_3/jwks",
  // 1.3 specific. List of LTI scopes requested by the tool
  "scopes": ["https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"],
  // 1.3 specific. List of possible launch URLs for after the Canvas authorize
  // redirect step
  "redirect_uris": ["https://mytool.com/launch", "https://mytool.com/1_3/launch"],
  // Default launch settings for all placements
  "launch_settings": {"message_type":"LtiResourceLinkRequest"},
  // List of placements configured by the tool
  "placements": [{"type":"Lti::Placement"}]
}
```

### A Lti::LaunchSettings object looks like:

``` example
// Default launch settings for all placements
{
  // Default message type for all placements
  "message_type": "LtiResourceLinkRequest",
  // The text of the link to the tool (if applicable).
  "text": "Hello World",
  // Canvas-specific i18n for placement text. See the Navigation Placement docs.
  "labels": {"en":"Hello World","es":"Hola Mundo"},
  // Placement-specific custom fields to send in the launch. Merged with
  // tool-level custom fields.
  "custom_fields": {"special_placement_thing":"foo1234"},
  // Default iframe height. Not valid for all placements. Overrides tool-level
  // launch_height.
  "selection_height": 800,
  // Default iframe width. Not valid for all placements. Overrides tool-level
  // launch_width.
  "selection_width": 1000,
  // Default iframe height. Not valid for all placements. Overrides tool-level
  // launch_height.
  "launch_height": 800,
  // Default iframe width. Not valid for all placements. Overrides tool-level
  // launch_width.
  "launch_width": 1000,
  // Default icon URL. Not valid for all placements. Overrides tool-level
  // icon_url.
  "icon_url": "https://mytool.com/icon.png",
  // The HTML class name of an InstUI Icon. Used instead of an icon_url in select
  // placements.
  "canvas_icon_class": "icon-lti",
  // Comma-separated list of Canvas permission short names required for a user to
  // launch from this placement.
  "required_permissions": "manage_course_content_edit,manage_course_content_read",
  // When set to '_blank', opens placement in a new tab.
  "windowTarget": "_blank",
  // The Canvas layout to use when launching the tool. See the Navigation
  // Placement docs.
  "display_type": "full_width_in_context",
  // The 1.1 launch URL for this placement. Overrides tool-level url.
  "url": "https://mytool.com/launch?placement=course_navigation",
  // The 1.3 launch URL for this placement. Overrides tool-level target_link_uri.
  "target_link_uri": "https://mytool.com/launch?placement=course_navigation",
  // Specifies types of users that can see this placement. Only valid for some
  // placements like course_navigation.
  "visibility": "admins",
  // 1.1 specific. If true, the tool will send the SIS email in the
  // lis_person_contact_email_primary launch property
  "prefer_sis_email": false,
  // 1.1 specific. If true, query parameters from the launch URL will not be
  // copied to the POST body.
  "oauth_compliant": true,
  // An SVG to use instead of an icon_url. Only valid for global_navigation.
  "icon_svg_path_64": "M100,37L70.1,10.5v176H37...",
  // Default display state for course_navigation. If 'enabled', will show in
  // course sidebar. If 'disabled', will be hidden.
  "default": "disabled",
  // Comma-separated list of media types that the tool can accept. Only valid for
  // file_item.
  "accept_media_types": "image/*,video/*",
  // If true, the tool will be launched in the tray. Only used by the
  // editor_button placement.
  "use_tray": true
}
```

### A Lti::Placement object looks like:

``` example
// The tool's configuration for a specific placement
{
  // The name of the placement.
  "placement": "course_navigation",
  // If true, the tool will show in this placement. If false, it will not.
  "enabled": true,
  // Default message type for all placements
  "message_type": "LtiResourceLinkRequest",
  // The text of the link to the tool (if applicable).
  "text": "Hello World",
  // Canvas-specific i18n for placement text. See the Navigation Placement docs.
  "labels": {"en":"Hello World","es":"Hola Mundo"},
  // Placement-specific custom fields to send in the launch. Merged with
  // tool-level custom fields.
  "custom_fields": {"special_placement_thing":"foo1234"},
  // Default iframe height. Not valid for all placements. Overrides tool-level
  // launch_height.
  "selection_height": 800,
  // Default iframe width. Not valid for all placements. Overrides tool-level
  // launch_width.
  "selection_width": 1000,
  // Default iframe height. Not valid for all placements. Overrides tool-level
  // launch_height.
  "launch_height": 800,
  // Default iframe width. Not valid for all placements. Overrides tool-level
  // launch_width.
  "launch_width": 1000,
  // Default icon URL. Not valid for all placements. Overrides tool-level
  // icon_url.
  "icon_url": "https://mytool.com/icon.png",
  // The HTML class name of an InstUI Icon. Used instead of an icon_url in select
  // placements.
  "canvas_icon_class": "icon-lti",
  // Comma-separated list of Canvas permission short names required for a user to
  // launch from this placement.
  "required_permissions": "manage_course_content_edit,manage_course_content_read",
  // When set to '_blank', opens placement in a new tab.
  "windowTarget": "_blank",
  // The Canvas layout to use when launching the tool. See the Navigation
  // Placement docs.
  "display_type": "full_width_in_context",
  // The 1.1 launch URL for this placement. Overrides tool-level url.
  "url": "https://mytool.com/launch?placement=course_navigation",
  // The 1.3 launch URL for this placement. Overrides tool-level target_link_uri.
  "target_link_uri": "https://mytool.com/launch?placement=course_navigation",
  // Specifies types of users that can see this placement. Only valid for some
  // placements like course_navigation.
  "visibility": "admins",
  // 1.1 specific. If true, the tool will send the SIS email in the
  // lis_person_contact_email_primary launch property
  "prefer_sis_email": false,
  // (Only applies to 1.1) If true, Canvas will not copy launch URL query
  // parameters to the POST body.
  "oauth_compliant": true,
  // An SVG to use instead of an icon_url. Only valid for global_navigation.
  "icon_svg_path_64": "M100,37L70.1,10.5v176H37...",
  // Default display state for course_navigation. If 'enabled', will show in
  // course sidebar. If 'disabled', will be hidden.
  "default": "disabled",
  // Comma-separated list of media types that the tool can accept. Only valid for
  // file_item.
  "accept_media_types": "image/*,video/*",
  // If true, the tool will be launched in the tray. Only used by the
  // editor_button placement.
  "use_tray": true
}
```

### A Lti::Overlay object looks like:

``` example
// Changes made by a Canvas admin to a tool's configuration.
{
  // The display name of the tool
  "title": "My Tool",
  // The description of the tool
  "description": "My Tool is built by me, for me.",
  // A key-value listing of all custom fields the tool has requested
  "custom_fields": {"context_title":"$Context.title","special_tool_thing":"foo1234"},
  // The default launch URL for the tool. Overridable by placements.
  "target_link_uri": "https://mytool.com/launch",
  // The tool's main domain. Highly recommended for deep linking, used to match
  // links to the tool.
  "domain": "mytool.com",
  // Canvas-defined privacy level for the tool
  "privacy_level": "public",
  // 1.3 specific. URL used for initial login request
  "oidc_initiation_url": "https://mytool.com/1_3/login",
  // 1.3 specific. List of LTI scopes that the tool has requested but an admin has
  // disabled
  "disabled_scopes": ["https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"],
  // List of placements that the tool has requested but an admin has disabled
  "disabled_placements": ["course_navigation"],
  // Placement-specific settings changed by an admin
  "placements": {"course_navigation":{"$ref":"Lti::Placement"}}
}
```

### A Lti::PlacementOverlay object looks like:

``` example
// Changes made by a Canvas admin to a tool's configuration for a specific
// placement.
{
  // The text of the link to the tool (if applicable).
  "text": "Hello World",
  // The default launch URL for the tool. Overridable by placements.
  "target_link_uri": "https://mytool.com/launch",
  // Default message type for all placements
  "message_type": "LtiResourceLinkRequest",
  // Default iframe height. Not valid for all placements. Overrides tool-level
  // launch_height.
  "launch_height": 800,
  // Default iframe width. Not valid for all placements. Overrides tool-level
  // launch_width.
  "launch_width": 1000,
  // Default icon URL. Not valid for all placements. Overrides tool-level
  // icon_url.
  "icon_url": "https://mytool.com/icon.png",
  // Default display state for course_navigation. If 'enabled', will show in
  // course sidebar. If 'disabled', will be hidden.
  "default": "disabled"
}
```

### A ListLtiRegistrationsResponse object looks like:

``` example
// The response for the List LTI Registrations API endpoint
{
  // The total number of LTI registrations across all pages
  "total": 1,
  // The paginated list of LTI::Registrations
  "data": [{"$ref":"Lti::Registration"}]
}
```

## List LTI Registrations in an account

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/accounts/:account_id/lti_registrations

**Scope:** `url:GET|/api/v1/accounts/:account_id/lti_registrations`

Returns all LTI registrations in the specified account. Includes registrations created in this account, those set to ‘allow’ from a parent root account (like Site Admin) and ‘on’ for this account, and those enabled ‘on’ at the parent root account level.

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>per_page</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The number of registrations to return per page. Defaults to 15.</p></td>
</tr>
<tr class="request-param">
<td>page</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The page number to return. Defaults to 1.</p></td>
</tr>
<tr class="request-param">
<td>sort</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The field to sort by. Choices are: name, nickname, lti_version, installed, installed_by, updated_by, updated, and on. Defaults to installed.</p></td>
</tr>
<tr class="request-param">
<td>dir</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The order to sort the given column by. Defaults to desc.</p>
<p>Allowed values: <code class="enum">asc</code>, <code class="enum">desc</code></p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional data to include. Always includes [account_binding].</p>
<dl>
<dt>“account_binding”</dt>
<dd>
<p>the registration’s binding to the given account</p>
</dd>
<dt>“configuration”</dt>
<dd>
<p>the registration’s Canvas-style tool configuration, without any overlays applied.</p>
</dd>
<dt>“overlaid_configuration”</dt>
<dd>
<p>the registration’s Canvas-style tool configuration, with all overlays applied.</p>
</dd>
<dt>“overlay”</dt>
<dd>
<p>the registration’s admin-defined configuration overlay</p>
</dd>
</dl></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would return the specified LTI registration
curl -X GET 'https://<canvas>/api/v1/accounts/<account_id>/registrations' \
     -H "Authorization: Bearer <token>"
```

Returns a [ListLtiRegistrationsResponse](lti_registrations.html#ListLtiRegistrationsResponse) object

## Show an LTI Registration

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/accounts/:account_id/lti_registrations/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/lti_registrations/:id`

Return details about the specified LTI registration, including the configuration and account binding.

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional data to include. Always includes [account_binding configuration].</p>
<dl>
<dt>“account_binding”</dt>
<dd>
<p>the registration’s binding to the given account</p>
</dd>
<dt>“configuration”</dt>
<dd>
<p>the registration’s Canvas-style tool configuration, without any overlays applied.</p>
</dd>
<dt>“overlaid_configuration”</dt>
<dd>
<p>the registration’s Canvas-style tool configuration, with all overlays applied.</p>
</dd>
<dt>“overlaid_legacy_configuration”</dt>
<dd>
<p>the registration’s legacy-style configuration, with all overlays applied.</p>
</dd>
<dt>“overlay”</dt>
<dd>
<p>the registration’s admin-defined configuration overlay</p>
</dd>
<dt>“overlay_versions”</dt>
<dd>
<p>the registration’s overlay’s edit history</p>
</dd>
</dl></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would return the specified LTI registration
curl -X GET 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations/<registration_id>' \
     -H "Authorization: Bearer <token>"
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Create an LTI Registration

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### POST /api/v1/accounts/:account_id/lti_registrations

**Scope:** `url:POST|/api/v1/accounts/:account_id/lti_registrations`

Create a new LTI Registration, as well as an associated Tool Configuration, Developer Key, and Registration Account binding. To install/create using Dynamic Registration, please use the \Dynamic Registration API.\

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>name</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the tool. If one isn’t provided, it will be inferred from the configuration’s title.</p></td>
</tr>
<tr class="request-param">
<td>admin_nickname</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A friendly nickname set by admins to override the tool name</p></td>
</tr>
<tr class="request-param">
<td>vendor</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The vendor of the tool</p></td>
</tr>
<tr class="request-param">
<td>description</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A description of the tool. Cannot exceed 2048 bytes.</p></td>
</tr>
<tr class="request-param">
<td>configuration</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>Required, Lti::ToolConfiguration | Lti::LegacyConfiguration</dt>
<dd>
<p>The LTI 1.3 configuration for the tool</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>overlay</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>Lti::Overlay</dt>
<dd>
<p>The overlay configuration for the tool. Overrides values in the base configuration.</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>unified_tool_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique identifier for the tool, used for analytics. If not provided, one will be generated.</p></td>
</tr>
<tr class="request-param">
<td>workflow_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The desired state for this registration/account binding. “allow” is only valid for Site Admin registrations. Defaults to “off”.</p>
<p>Allowed values: <code class="enum">on</code>, <code class="enum">off</code>, <code class="enum">allow</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would create a new LTI Registration, as well as an associated Developer Key
and LTI Tool Configuration.

curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations' \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{
          "vendor": "Example",
          "name": "An Example Tool",
          "admin_nickname": "A Great LTI Tool",
          "configuration": {
            "title": "Sample Tool",
            "description": "A sample LTI tool",
            "target_link_uri": "https://example.com/launch",
            "oidc_initiation_url": "https://example.com/oidc",
            "redirect_uris": ["https://example.com/redirect"],
            "scopes": ["https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"],
            "placements": [
              {
                "placement": "course_navigation",
                "enabled": true
              }
            ],
            "launch_settings": {}
          }
        }'
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Show an LTI Registration (via the client_id)

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/accounts/:account_id/lti_registration_by_client_id/:client_id

**Scope:** `url:GET|/api/v1/accounts/:account_id/lti_registration_by_client_id/:client_id`

Returns details about the specified LTI registration, including the configuration and account binding.

#### Example Request:

####

``` example
This would return the specified LTI registration
curl -X GET 'https://<canvas>/api/v1/accounts/<account_id>/lti_registration_by_client_id/<client_id>' \
     -H "Authorization: Bearer <token>"
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Update an LTI Registration

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### PUT /api/v1/accounts/:account_id/lti_registrations/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/lti_registrations/:id`

Update the specified LTI registration with the provided parameters. Note that updating the base tool configuration of a registration that is associated with a Dynamic Registration will return a 422. All other fields can be updated freely.

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>name</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the tool</p></td>
</tr>
<tr class="request-param">
<td>admin_nickname</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The admin-configured friendly display name for the registration</p></td>
</tr>
<tr class="request-param">
<td>description</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A description of the tool. Cannot exceed 2048 bytes.</p></td>
</tr>
<tr class="request-param">
<td>configuration</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>Lti::ToolConfiguration | Lti::LegacyConfiguration</dt>
<dd>
<p>The LTI 1.3 configuration for the tool. Note that updating the base tool configuration of a registration associated with a Dynamic Registration is not allowed.</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>overlay</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>Lti::Overlay</dt>
<dd>
<p>The overlay configuration for the tool. Overrides values in the base configuration. Note that updating the overlay of a registration associated with a Dynamic Registration IS allowed.</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>workflow_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The desired state for this registration/account binding. “allow” is only valid for Site Admin registrations.</p>
<p>Allowed values: <code class="enum">on</code>, <code class="enum">off</code>, <code class="enum">allow</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would update the specified LTI Registration, as well as its associated Developer Key
and LTI Tool Configuration.

curl -X PUT 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations/<registration_id>' \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{
          "vendor": "Example",
          "name": "An Example Tool",
          "admin_nickname": "A Great LTI Tool",
          "configuration": {
            "title": "Sample Tool",
            "description": "A sample LTI tool",
            "target_link_uri": "https://example.com/launch",
            "oidc_initiation_url": "https://example.com/oidc",
            "redirect_uris": ["https://example.com/redirect"],
            "scopes": ["https://purl.imsglobal.org/spec/lti-ags/scope/lineitem"],
            "placements": [
              {
                "placement": "course_navigation",
                "enabled": true
              }
            ],
            "launch_settings": {}
          }
        }'
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Reset an LTI Registration to Defaults

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### PUT /api/v1/accounts/:account_id/lti_registrations/:id/reset

**Scope:** `url:PUT|/api/v1/accounts/:account_id/lti_registrations/:id/reset`

Reset the specified LTI registration to its default settings in this context. This removes all customizations that were present in the overlay associated with this context.

#### Example Request:

####

``` example
This would reset the specified LTI registration to its default settings
curl -X PUT 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations/<registration_id>/reset' \
     -H "Authorization: Bearer <token>"
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Delete an LTI Registration

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### DELETE /api/v1/accounts/:account_id/lti_registrations/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/lti_registrations/:id`

Remove the specified LTI registration

#### Example Request:

####

``` example
This would delete the specified LTI registration
curl -X DELETE 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations/<registration_id>' \
     -H "Authorization: Bearer <token>"
```

Returns a [Lti::Registration](lti_registrations.html#Lti::Registration) object

## Bind an LTI Registration to an Account

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### POST /api/v1/accounts/:account_id/lti_registrations/:id/bind

**Scope:** `url:POST|/api/v1/accounts/:account_id/lti_registrations/:id/bind`

Enable or disable the specified LTI registration for the specified account. To enable an inherited registration (eg from Site Admin), pass the registration’s global ID.

Only allowed for root accounts.

**Specifics for Site Admin:** “on” enables and locks the registration on for all root accounts. “off” disables and hides the registration for all root accounts. “allow” makes the registration visible to all root accounts, but accounts must bind it to use it.

**Specifics for centrally-managed/federated consortia:** Child root accounts may only bind registrations created in the same account. For parent root account, binding also applies to all child root accounts.

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>workflow_state</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The desired state for this registration/account binding. “allow” is only valid for Site Admin registrations.</p>
<p>Allowed values: <code class="enum">on</code>, <code class="enum">off</code>, <code class="enum">allow</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would enable the specified LTI registration for the specified account
curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/lti_registrations/<registration_id>/bind' \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"workflow_state": "on"}'
```
