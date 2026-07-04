# Quiz Submission Files API

## Upload a file

### POST /api/v1/courses/:course_id/quizzes/:quiz_id/submissions/self/files

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/self/files`

Associate a new quiz submission file

This API endpoint is the first step in uploading a quiz submission file. See the [File Upload Documentation](file_uploads.html "File Upload Documentation") for details on the file upload workflow as these parameters are interpreted as per the documentation there.

#### Request Parameters:

| Parameter    |     | Type   | Description                          |
|--------------|-----|--------|--------------------------------------|
| name         |     | string | The name of the quiz submission file |
| on_duplicate |     | string | How to handle duplicate names        |

#### Example Response:

####

``` example
{
  "attachments": [
    {
      "upload_url": "https://some-bucket.s3.amazonaws.com/",
      "upload_params": {
        "key": "/users/1234/files/answer_pic.jpg",
        "acl": "private",
        "Filename": "answer_pic.jpg",
        "AWSAccessKeyId": "some_id",
        "Policy": "some_opaque_string",
        "Signature": "another_opaque_string",
        "Content-Type": "image/jpeg"
      }
    }
  ]
}
```
