# Plagiarism Detection Platform Users API

**Plagiarism Detection Platform API for Users (Must use [JWT access tokens](jwt_access_tokens.html) with this API).**

## Get a single user (lti)

### GET /api/lti/users/:id

**Scope:** `url:GET|/api/lti/users/:id`

Get a single Canvas user by Canvas id or LTI id. Tool providers may only access users that have been assigned an assignment associated with their tool.

Returns an [User](users.html#User) object

## Get all users in a group (lti)

### GET /api/lti/groups/:group_id/users

**Scope:** `url:GET|/api/lti/groups/:group_id/users`

Get all Canvas users in a group. Tool providers may only access groups that belong to the context the tool is installed in.

Returns a list of [User](users.html#User) objects
