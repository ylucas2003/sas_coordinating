# External Tools API

API for accessing and configuring external tools on accounts and courses. "External tools" are IMS LTI links: <http://www.imsglobal.org/developers/LTI/index.cfm>

NOTE: Placements not documented here should be considered beta features and are not officially supported.

## List external tools

### GET /api/v1/courses/:course_id/external_tools

**Scope:** `url:GET|/api/v1/courses/:course_id/external_tools`

### GET /api/v1/accounts/:account_id/external_tools

**Scope:** `url:GET|/api/v1/accounts/:account_id/external_tools`

### GET /api/v1/groups/:group_id/external_tools

**Scope:** `url:GET|/api/v1/groups/:group_id/external_tools`

Returns the paginated list of external tools for the current context. See the get request docs for a single tool for a list of properties on an external tool.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| search_term |  | string | The partial name of the tools to match and return. |
| selectable |  | boolean | If true, then only tools that are meant to be selectable are returned. |
| include_parents |  | boolean | If true, then include tools installed in all accounts above the current context |
| placement |  | string | The placement type to filter by. |

#### Example Request:

####

``` example
Return all tools at the current context as well as all tools from the parent, and filter the tools list to only those with a placement of 'editor_button'
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools?include_parents=true&placement=editor_button' \
     -H "Authorization: Bearer <token>"
```

#### Example Response:

####

``` example
[
 {
   "id": 1,
   "domain": "domain.example.com",
   "url": "http://www.example.com/ims/lti",
   "consumer_key": "key",
   "name": "LTI Tool",
   "description": "This is for cool things",
   "created_at": "2037-07-21T13:29:31Z",
   "updated_at": "2037-07-28T19:38:31Z",
   "privacy_level": "anonymous",
   "custom_fields": {"key": "value"},
   "is_rce_favorite": false,
   "is_top_nav_favorite": false,
   "account_navigation": {
        "canvas_icon_class": "icon-lti",
        "icon_url": "...",
        "text": "...",
        "url": "...",
        "label": "...",
        "selection_width": 50,
        "selection_height":50
   },
   "assignment_selection": null,
   "course_home_sub_navigation": null,
   "course_navigation": {
        "canvas_icon_class": "icon-lti",
        "icon_url": "...",
        "text": "...",
        "url": "...",
        "default": "disabled",
        "enabled": "true",
        "visibility": "public",
        "windowTarget": "_blank"
   },
   "editor_button": {
        "canvas_icon_class": "icon-lti",
        "icon_url": "...",
        "message_type": "ContentItemSelectionRequest",
        "text": "...",
        "url": "...",
        "label": "...",
        "selection_width": 50,
        "selection_height": 50
   },
   "homework_submission": null,
   "link_selection": null,
   "migration_selection": null,
   "resource_selection": null,
   "tool_configuration": null,
   "user_navigation": null,
   "selection_width": 500,
   "selection_height": 500,
   "icon_url": "...",
   "not_selectable": false,
   "deployment_id": null,
   "unified_tool_id": null
 },
 { ...  }
]
```

## Get a sessionless launch url for an external tool.

### GET /api/v1/courses/:course_id/external_tools/sessionless_launch

**Scope:** `url:GET|/api/v1/courses/:course_id/external_tools/sessionless_launch`

### GET /api/v1/accounts/:account_id/external_tools/sessionless_launch

**Scope:** `url:GET|/api/v1/accounts/:account_id/external_tools/sessionless_launch`

Returns a sessionless launch url for an external tool. Prefers the resource_link_lookup_uuid, but defaults to the other passed

``` code
parameters id, url, and launch_type
```

NOTE: Either the resource_link_lookup_uuid, id, or url must be provided unless launch_type is assessment or module_item.

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
<td>id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The external id of the tool to launch.</p></td>
</tr>
<tr class="request-param">
<td>url</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The LTI launch url for the external tool.</p></td>
</tr>
<tr class="request-param">
<td>assignment_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The assignment id for an assignment launch. Required if launch_type is set to “assessment”.</p></td>
</tr>
<tr class="request-param">
<td>module_item_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The assignment id for a module item launch. Required if launch_type is set to “module_item”.</p></td>
</tr>
<tr class="request-param">
<td>launch_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of launch to perform on the external tool. Placement names (eg. “course_navigation”) can also be specified to use the custom launch url for that placement; if done, the tool id must be provided.</p>
<p>Allowed values: <code class="enum">assessment</code>, <code class="enum">module_item</code></p></td>
</tr>
<tr class="request-param">
<td>resource_link_lookup_uuid</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The identifier to lookup a resource link.</p></td>
</tr>
</tbody>
</table>

#### API response field:

-  id

  The id for the external tool to be launched.

-  name

  The name of the external tool to be launched.

-  url

  The url to load to launch the external tool for the user.

#### Example Request:

####

``` example
Finds the tool by id and returns a sessionless launch url
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/sessionless_launch' \
     -H "Authorization: Bearer <token>" \
     -F 'id=<external_tool_id>'
```

####

``` example
Finds the tool by launch url and returns a sessionless launch url
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/sessionless_launch' \
     -H "Authorization: Bearer <token>" \
     -F 'url=<lti launch url>'
```

####

``` example
Finds the tool associated with a specific assignment and returns a sessionless launch url
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/sessionless_launch' \
     -H "Authorization: Bearer <token>" \
     -F 'launch_type=assessment' \
     -F 'assignment_id=<assignment_id>'
```

####

``` example
Finds the tool associated with a specific module item and returns a sessionless launch url
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/sessionless_launch' \
     -H "Authorization: Bearer <token>" \
     -F 'launch_type=module_item' \
     -F 'module_item_id=<module_item_id>'
```

####

``` example
Finds the tool by id and returns a sessionless launch url for a specific placement
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/sessionless_launch' \
     -H "Authorization: Bearer <token>" \
     -F 'id=<external_tool_id>' \
     -F 'launch_type=<placement_name>'
```

## Get a single external tool

### GET /api/v1/courses/:course_id/external_tools/:external_tool_id

**Scope:** `url:GET|/api/v1/courses/:course_id/external_tools/:external_tool_id`

### GET /api/v1/accounts/:account_id/external_tools/:external_tool_id

**Scope:** `url:GET|/api/v1/accounts/:account_id/external_tools/:external_tool_id`

Returns the specified external tool.

#### API response field:

-  id

  The unique identifier for the tool

-  domain

  The domain to match links against

-  url

  The url to match links against

-  consumer_key

  The consumer key used by the tool (The associated shared secret is not returned)

-  name

  The name of the tool

-  description

  A description of the tool

-  created_at

  Timestamp of creation

-  updated_at

  Timestamp of last update

-  privacy_level

  How much user information to send to the external tool: “anonymous”, “name_only”, “email_only”, “public”

-  custom_fields

  Custom fields that will be sent to the tool consumer

-  is_rce_favorite

  Boolean determining whether this tool should be in a preferred location in the RCE.

-  is_top_nav_favorite

  Boolean determining whether this tool should have a dedicated button in Top Navigation.

-  account_navigation

  The configuration for account navigation links (see create API for values)

-  assignment_selection

  The configuration for assignment selection links (see create API for values)

-  course_home_sub_navigation

  The configuration for course home navigation links (see create API for values)

-  course_navigation

  The configuration for course navigation links (see create API for values)

-  editor_button

  The configuration for a WYSIWYG editor button (see create API for values)

-  homework_submission

  The configuration for homework submission selection (see create API for values)

-  link_selection

  The configuration for link selection (see create API for values)

-  migration_selection

  The configuration for migration selection (see create API for values)

-  resource_selection

  The configuration for a resource selector in modules (see create API for values)

-  tool_configuration

  The configuration for a tool configuration link (see create API for values)

-  user_navigation

  The configuration for user navigation links (see create API for values)

-  selection_width

  The pixel width of the iFrame that the tool will be rendered in

-  selection_height

  The pixel height of the iFrame that the tool will be rendered in

-  icon_url

  The url for the tool icon

-  not_selectable

  whether the tool is not selectable from assignment and modules

-  unified_tool_id

  The unique identifier for the tool in LearnPlatform

-  deployment_id

  The unique identifier for the deployment of the tool

#### Example Response:

####

``` example
{
  "id": 1,
  "domain": "domain.example.com",
  "url": "http://www.example.com/ims/lti",
  "consumer_key": "key",
  "name": "LTI Tool",
  "description": "This is for cool things",
  "created_at": "2037-07-21T13:29:31Z",
  "updated_at": "2037-07-28T19:38:31Z",
  "privacy_level": "anonymous",
  "custom_fields": {"key": "value"},
  "account_navigation": {
       "canvas_icon_class": "icon-lti",
       "icon_url": "...",
       "text": "...",
       "url": "...",
       "label": "...",
       "selection_width": 50,
       "selection_height":50
  },
  "assignment_selection": null,
  "course_home_sub_navigation": null,
  "course_navigation": {
       "canvas_icon_class": "icon-lti",
       "icon_url": "...",
       "text": "...",
       "url": "...",
       "default": "disabled",
       "enabled": "true",
       "visibility": "public",
       "windowTarget": "_blank"
  },
  "editor_button": {
       "canvas_icon_class": "icon-lti",
       "icon_url": "...",
       "message_type": "ContentItemSelectionRequest",
       "text": "...",
       "url": "...",
       "label": "...",
       "selection_width": 50,
       "selection_height": 50
  },
  "homework_submission": null,
  "link_selection": null,
  "migration_selection": null,
  "resource_selection": null,
  "tool_configuration": null,
  "user_navigation": {
       "canvas_icon_class": "icon-lti",
       "icon_url": "...",
       "text": "...",
       "url": "...",
       "default": "disabled",
       "enabled": "true",
       "visibility": "public"
  },
  "selection_width": 500,
  "selection_height": 500,
  "icon_url": "...",
  "not_selectable": false
}
```

## Create an external tool

### POST /api/v1/courses/:course_id/external_tools

**Scope:** `url:POST|/api/v1/courses/:course_id/external_tools`

### POST /api/v1/accounts/:account_id/external_tools

**Scope:** `url:POST|/api/v1/accounts/:account_id/external_tools`

Create an external tool in the specified course/account. The created tool will be returned, see the “show” endpoint for an example. If a client ID is supplied canvas will attempt to create a context external tool using the LTI 1.3 standard.

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
<td>client_id</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The client id is attached to the developer key. If supplied all other parameters are unnecessary and will be ignored</p></td>
</tr>
<tr class="request-param">
<td>name</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The name of the tool</p></td>
</tr>
<tr class="request-param">
<td>privacy_level</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>How much user information to send to the external tool.</p>
<p>Allowed values: <code class="enum">anonymous</code>, <code class="enum">name_only</code>, <code class="enum">email_only</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>consumer_key</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The consumer key for the external tool</p></td>
</tr>
<tr class="request-param">
<td>shared_secret</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The shared secret with the external tool</p></td>
</tr>
<tr class="request-param">
<td>description</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A description of the tool</p></td>
</tr>
<tr class="request-param">
<td>url</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url to match links against. Either “url” or “domain” should be set, not both.</p></td>
</tr>
<tr class="request-param">
<td>domain</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The domain to match links against. Either “url” or “domain” should be set, not both.</p></td>
</tr>
<tr class="request-param">
<td>icon_url</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the icon to show for this tool</p></td>
</tr>
<tr class="request-param">
<td>text</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The default text to show for this tool</p></td>
</tr>
<tr class="request-param">
<td>custom_fields[field_name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Custom fields that will be sent to the tool consumer; can be used multiple times</p></td>
</tr>
<tr class="request-param">
<td>is_rce_favorite</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>(Deprecated in favor of Add tool to RCE Favorites and Remove tool from RCE Favorites) Whether this tool should appear in a preferred location in the RCE. This only applies to tools in root account contexts that have an editor button placement.</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool for account navigation</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show on the left-tab in the account navigation</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[selection_width]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The width of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[selection_height]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The height of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>account_navigation[display_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The layout type to use when launching the tool. Must be “full_width”, “full_width_in_context”, “full_width_with_nav”, “in_nav_context”, “borderless”, or “default”</p></td>
</tr>
<tr class="request-param">
<td>user_navigation[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool for user navigation</p></td>
</tr>
<tr class="request-param">
<td>user_navigation[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>user_navigation[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show on the left-tab in the user navigation</p></td>
</tr>
<tr class="request-param">
<td>user_navigation[visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Who will see the navigation tab. “admins” for admins, “public” or “members” for everyone. Setting this to ‘null` will remove this configuration and use the default behavior, which is “public”.</p>
<p>Allowed values: <code class="enum">admins</code>, <code class="enum">members</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>course_home_sub_navigation[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool for right-side course home navigation menu</p></td>
</tr>
<tr class="request-param">
<td>course_home_sub_navigation[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>course_home_sub_navigation[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show on the right-side course home navigation menu</p></td>
</tr>
<tr class="request-param">
<td>course_home_sub_navigation[icon_url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the icon to show in the right-side course home navigation menu</p></td>
</tr>
<tr class="request-param">
<td>course_navigation[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>course_navigation[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show on the left-tab in the course navigation</p></td>
</tr>
<tr class="request-param">
<td>course_navigation[visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Who will see the navigation tab. “admins” for course admins, “members” for students, “public” for everyone. Setting this to ‘null` will remove this configuration and use the default behavior, which is “public”.</p>
<p>Allowed values: <code class="enum">admins</code>, <code class="enum">members</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>course_navigation[windowTarget]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Determines how the navigation tab will be opened. “_blank” Launches the external tool in a new window or tab. “_self” (Default) Launches the external tool in an iframe inside of Canvas.</p>
<p>Allowed values: <code class="enum">_blank</code>, <code class="enum">_self</code></p></td>
</tr>
<tr class="request-param">
<td>course_navigation[default]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set to “disabled” the tool will not appear in the course navigation until a teacher explicitly enables it.</p>
<p>If set to “enabled” the tool will appear in the course navigation without requiring a teacher to explicitly enable it.</p>
<p>defaults to “enabled”</p>
<p>Allowed values: <code class="enum">disabled</code>, <code class="enum">enabled</code></p></td>
</tr>
<tr class="request-param">
<td>course_navigation[display_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The layout type to use when launching the tool. Must be “full_width”, “full_width_in_context”, “full_width_with_nav”, “in_nav_context”, “borderless”, or “default”</p></td>
</tr>
<tr class="request-param">
<td>editor_button[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>editor_button[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>editor_button[icon_url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the icon to show in the WYSIWYG editor</p></td>
</tr>
<tr class="request-param">
<td>editor_button[selection_width]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The width of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>editor_button[selection_height]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The height of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>editor_button[message_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set this to ContentItemSelectionRequest to tell the tool to use content-item; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>homework_submission[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>homework_submission[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>homework_submission[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show on the homework submission tab</p></td>
</tr>
<tr class="request-param">
<td>homework_submission[message_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set this to ContentItemSelectionRequest to tell the tool to use content-item; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>link_selection[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>link_selection[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>link_selection[text]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The text that will show for the link selection text</p></td>
</tr>
<tr class="request-param">
<td>link_selection[message_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set this to ContentItemSelectionRequest to tell the tool to use content-item; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>migration_selection[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>migration_selection[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>migration_selection[message_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set this to ContentItemSelectionRequest to tell the tool to use content-item; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>tool_configuration[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>tool_configuration[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature</p></td>
</tr>
<tr class="request-param">
<td>tool_configuration[message_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set this to ContentItemSelectionRequest to tell the tool to use content-item; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>tool_configuration[prefer_sis_email]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to default the lis_person_contact_email_primary to prefer provisioned sis_email; otherwise, omit</p></td>
</tr>
<tr class="request-param">
<td>resource_selection[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the external tool</p></td>
</tr>
<tr class="request-param">
<td>resource_selection[enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set this to enable this feature. If set to false, not_selectable must also be set to true in order to hide this tool from the selection UI in modules and assignments.</p></td>
</tr>
<tr class="request-param">
<td>resource_selection[icon_url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The url of the icon to show in the module external tool list</p></td>
</tr>
<tr class="request-param">
<td>resource_selection[selection_width]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The width of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>resource_selection[selection_height]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The height of the dialog the tool is launched in</p></td>
</tr>
<tr class="request-param">
<td>config_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Configuration can be passed in as CC xml instead of using query parameters. If this value is “by_url” or “by_xml” then an xml configuration will be expected in either the “config_xml” or “config_url” parameter. Note that the name parameter overrides the tool name provided in the xml</p></td>
</tr>
<tr class="request-param">
<td>config_xml</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>XML tool configuration, as specified in the CC xml specification. This is required if “config_type” is set to “by_xml”</p></td>
</tr>
<tr class="request-param">
<td>config_url</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>URL where the server can retrieve an XML tool configuration, as specified in the CC xml specification. This is required if “config_type” is set to “by_url”</p></td>
</tr>
<tr class="request-param">
<td>not_selectable</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default: false. If set to true, and if resource_selection is set to false, the tool won’t show up in the external tool selection UI in modules and assignments</p></td>
</tr>
<tr class="request-param">
<td>oauth_compliant</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default: false, if set to true LTI query params will not be copied to the post body.</p></td>
</tr>
<tr class="request-param">
<td>unified_tool_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique identifier for the tool in LearnPlatform</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
This would create a tool on this course with two custom fields and a course navigation tab
curl -X POST 'https://<canvas>/api/v1/courses/<course_id>/external_tools' \
     -H "Authorization: Bearer <token>" \
     -F 'name=LTI Example' \
     -F 'consumer_key=asdfg' \
     -F 'shared_secret=lkjh' \
     -F 'url=https://example.com/ims/lti' \
     -F 'privacy_level=name_only' \
     -F 'custom_fields[key1]=value1' \
     -F 'custom_fields[key2]=value2' \
     -F 'course_navigation[text]=Course Materials' \
     -F 'course_navigation[enabled]=true'
```

####

``` example
This would create a tool on the account with navigation for the user profile page
curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/external_tools' \
     -H "Authorization: Bearer <token>" \
     -F 'name=LTI Example' \
     -F 'consumer_key=asdfg' \
     -F 'shared_secret=lkjh' \
     -F 'url=https://example.com/ims/lti' \
     -F 'privacy_level=name_only' \
     -F 'user_navigation[url]=https://example.com/ims/lti/user_endpoint' \
     -F 'user_navigation[text]=Something Cool'
     -F 'user_navigation[enabled]=true'
```

####

``` example
This would create a tool on the account with configuration pulled from an external URL
curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/external_tools' \
     -H "Authorization: Bearer <token>" \
     -F 'name=LTI Example' \
     -F 'consumer_key=asdfg' \
     -F 'shared_secret=lkjh' \
     -F 'config_type=by_url' \
     -F 'config_url=https://example.com/ims/lti/tool_config.xml'
```

## Edit an external tool

### PUT /api/v1/courses/:course_id/external_tools/:external_tool_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/external_tools/:external_tool_id`

### PUT /api/v1/accounts/:account_id/external_tools/:external_tool_id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/external_tools/:external_tool_id`

Update the specified external tool. Uses same parameters as create

#### Example Request:

####

``` example
This would update the specified keys on this external tool
curl -X PUT 'https://<canvas>/api/v1/courses/<course_id>/external_tools/<external_tool_id>' \
     -H "Authorization: Bearer <token>" \
     -F 'name=Public Example' \
     -F 'privacy_level=public'
```

## Delete an external tool

### DELETE /api/v1/courses/:course_id/external_tools/:external_tool_id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/external_tools/:external_tool_id`

### DELETE /api/v1/accounts/:account_id/external_tools/:external_tool_id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/external_tools/:external_tool_id`

Remove the specified external tool

#### Example Request:

####

``` example
This would delete the specified external tool
curl -X DELETE 'https://<canvas>/api/v1/courses/<course_id>/external_tools/<external_tool_id>' \
     -H "Authorization: Bearer <token>"
```

## Add tool to RCE Favorites

### POST /api/v1/accounts/:account_id/external_tools/rce_favorites/:id

**Scope:** `url:POST|/api/v1/accounts/:account_id/external_tools/rce_favorites/:id`

Add the specified editor_button external tool to a preferred location in the RCE for courses in the given account and its subaccounts (if the subaccounts haven’t set their own RCE Favorites). Cannot set more than 2 RCE Favorites.

#### Example Request:

####

``` example
curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/external_tools/rce_favorites/<id>' \
     -H "Authorization: Bearer <token>"
```

## Remove tool from RCE Favorites

### DELETE /api/v1/accounts/:account_id/external_tools/rce_favorites/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/external_tools/rce_favorites/:id`

Remove the specified external tool from a preferred location in the RCE for the given account

#### Example Request:

####

``` example
curl -X DELETE 'https://<canvas>/api/v1/accounts/<account_id>/external_tools/rce_favorites/<id>' \
     -H "Authorization: Bearer <token>"
```

## Add tool to Top Navigation Favorites

### POST /api/v1/accounts/:account_id/external_tools/top_nav_favorites/:id

**Scope:** `url:POST|/api/v1/accounts/:account_id/external_tools/top_nav_favorites/:id`

Adds a dedicated button in Top Navigation for the specified tool for the given account. Cannot set more than 2 top_navigation Favorites.

#### Example Request:

####

``` example
curl -X POST 'https://<canvas>/api/v1/accounts/<account_id>/external_tools/top_nav_favorites/<id>' \
     -H "Authorization: Bearer <token>"
```

## Remove tool from Top Navigation Favorites

### DELETE /api/v1/accounts/:account_id/external_tools/top_nav_favorites/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/external_tools/top_nav_favorites/:id`

Removes the dedicated button in Top Navigation for the specified tool for the given account.

#### Example Request:

####

``` example
curl -X DELETE 'https://<canvas>/api/v1/accounts/<account_id>/external_tools/top_nav_favorites/<id>' \
     -H "Authorization: Bearer <token>"
```

## Get visible course navigation tools

### GET /api/v1/external_tools/visible_course_nav_tools

**Scope:** `url:GET|/api/v1/external_tools/visible_course_nav_tools`

Get a list of external tools with the course_navigation placement that have not been hidden in course settings and whose visibility settings apply to the requesting user. These tools are the same that appear in the course navigation.

The response format is the same as for List external tools, but with additional context_id and context_name fields on each element in the array.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| context_codes\[\] | Required | string | List of context_codes to retrieve visible course nav tools for (for example, `course_123`). Only courses are presently supported. |

#### API response field:

-  context_id

  The unique identifier of the associated context

-  context_name

  The name of the associated context

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/external_tools/visible_course_nav_tools?context_codes[]=course_5' \
     -H "Authorization: Bearer <token>"
```

#### Example Response:

####

``` example
[{
  "id": 1,
  "domain": "domain.example.com",
  "url": "http://www.example.com/ims/lti",
  "context_id": 5,
  "context_name": "Example Course",
  ...
},
{ ...  }]
```

## Get visible course navigation tools for a single course

### GET /api/v1/courses/:course_id/external_tools/visible_course_nav_tools

**Scope:** `url:GET|/api/v1/courses/:course_id/external_tools/visible_course_nav_tools`

Get a list of external tools with the course_navigation placement that have not been hidden in course settings and whose visibility settings apply to the requesting user. These tools are the same that appear in the course navigation.

The response format is the same as Get visible course navigation tools.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/external_tools/visible_course_nav_tools' \
     -H "Authorization: Bearer <token>"
```
