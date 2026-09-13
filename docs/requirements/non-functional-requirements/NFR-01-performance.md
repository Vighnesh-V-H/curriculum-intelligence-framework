# NFR-01: Performance

## Description

The system shall provide responsive performance for normal user operations and shall prevent long-running AI verification processes from blocking user requests.

## Performance Requirements

### Normal API Operations

For normal CRUD and system operations, the system should target:

- **95% of requests:** response time below **500 ms** under expected normal load.
- **99% of requests:** response time below **1 second** under expected normal load.

Examples of normal operations include:

- Creating a curriculum
- Updating curriculum information
- Adding a course
- Updating a course
- Removing a course
- Retrieving curriculum information
- Retrieving course information
- Submitting a curriculum
- Viewing verification results

### Search Operations

Search and filtering operations should target:

- **95% of requests:** response time below **1 second** under expected normal load.

This includes operations such as:

- Searching courses
- Searching curricula
- Filtering curriculum versions
- Searching verification findings

## AI Verification Processing

AI-based curriculum verification may require significantly more processing time than normal API operations.

The system shall:

- Process AI verification asynchronously.
- Avoid keeping a synchronous HTTP request open while AI verification is running.
- Immediately acknowledge a valid verification request.
- Provide a mechanism to determine the current verification status.
- Persist the verification results after processing is completed.
- Allow authorized users to retrieve the completed verification results.

Example flow:

```text
User
  │
  │ Start Verification
  ▼
API
  │
  ├── Accept Request
  │
  └── Start Background Processing
          │
          ▼
      AI Verification
          │
          ▼
      Save Results
          │
          ▼
   Verification Completed
```

The user should not be required to keep an HTTP request open until AI verification finishes.

## Performance Under Expected Load

The system shall maintain the defined response-time targets under the expected normal user load.

Performance requirements shall be evaluated using realistic workloads representing expected system usage.

## Performance Considerations

The following operations may require additional performance consideration:

- Large curriculum retrieval.
- Large syllabus/document processing.
- Curriculum version comparison.
- Searching across large amounts of curriculum data.
- AI-based curriculum verification.
- Generation and retrieval of verification reports.

Long-running operations should be handled asynchronously where appropriate.

## Measurement

Performance shall be measured from the time the system receives a request until an appropriate response is returned to the client.

For asynchronous operations, the initial API response time and background processing time shall be measured separately.

## Acceptance Criteria

The system shall be considered compliant when:

- Normal API operations meet the defined response-time targets under expected normal load.
- Search operations meet the defined response-time targets under expected normal load.
- AI verification does not require a long-running synchronous HTTP request.
- Users can determine whether an AI verification request is queued, processing, completed, or failed.
- Completed AI verification results are available for authorized users.
