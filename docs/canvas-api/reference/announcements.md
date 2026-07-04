# Announcements API

API for retrieving announcements. This API is Announcement-specific. See also the Discussion Topics API, which operates on Announcements also.

## List announcements

### GET /api/v1/announcements

**Scope:** `url:GET|/api/v1/announcements`

Returns the paginated list of announcements for the given courses and date range. Note that a `context_code` field is added to the responses so you can tell which course each announcement belongs to.

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
<td>context_codes[]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>List of context_codes to retrieve announcements for (for example, <code>course_123</code>). Only courses are presently supported. The call will fail unless the caller has View Announcements permission in all listed courses.</p></td>
</tr>
<tr class="request-param">
<td>start_date</td>
<td></td>
<td>Date</td>
<td class="param-desc"><p>Only return announcements posted since the start_date (inclusive). Defaults to 14 days ago. The value should be formatted as: yyyy-mm-dd or ISO 8601 YYYY-MM-DDTHH:MM:SSZ.</p></td>
</tr>
<tr class="request-param">
<td>end_date</td>
<td></td>
<td>Date</td>
<td class="param-desc"><p>Only return announcements posted before the end_date (inclusive). Defaults to 28 days from start_date. The value should be formatted as: yyyy-mm-dd or ISO 8601 YYYY-MM-DDTHH:MM:SSZ. Announcements scheduled for future posting will only be returned to course administrators.</p></td>
</tr>
<tr class="request-param">
<td>available_after</td>
<td></td>
<td>Date</td>
<td class="param-desc"><p>Only return announcements having locked_at nil or after available_after (exclusive). The value should be formatted as: yyyy-mm-dd or ISO 8601 YYYY-MM-DDTHH:MM:SSZ. Effective only for students (who don’t have moderate forum right).</p></td>
</tr>
<tr class="request-param">
<td>active_only</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Only return active announcements that have been published. Applies only to requesting users that have permission to view unpublished items. Defaults to false for users with access to view unpublished items, otherwise true and unmodifiable.</p></td>
</tr>
<tr class="request-param">
<td>latest_only</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Only return the latest announcement for each associated context. The response will include at most one announcement for each specified context in the context_codes[] parameter. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>include</td>
<td></td>
<td>array</td>
<td class="param-desc"><p>Optional list of resources to include with the response. May include a string of the name of the resource. Possible values are: “sections”, “sections_user_count” if “sections” is passed, includes the course sections that are associated with the topic, if the topic is specific to certain sections of the course. If “sections_user_count” is passed, then:</p>
`(a) If sections were asked for *and* the topic is specific to certain
    course sections sections, includes the number of users in each
    section. (as part of the section json asked for above)
(b) Else, includes at the root level the total number of users in the
    topic's context (group or course) that the topic applies to.`</td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/announcements?context_codes[]=course_1&context_codes[]=course_2 \
     -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
[{
  "id": 1,
  "title": "Hear ye",
  "message": "Henceforth, all assignments must be...",
  "posted_at": "2017-01-31T22:00:00Z",
  "delayed_post_at": null,
  "context_code": "course_2",
  ...
}]
```

Returns a list of [DiscussionTopic](discussion_topics.html#DiscussionTopic) objects
