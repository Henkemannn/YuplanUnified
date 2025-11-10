# Admin Module — System Administration & Data Management

The Admin module provides comprehensive system administration capabilities for site management, department configuration, dietary defaults, menu imports, and bulk operations.

## Core Flows

### Site & Department Management
1. **Site Creation**: Admin creates new sites with basic metadata
2. **Department Setup**: Admin adds departments to sites with attendance defaults
3. **Configuration Updates**: Admin modifies department settings, notes, and dietary defaults
4. **Bulk Operations**: Admin performs batch updates across multiple departments

### Menu Import Pipeline
1. **Import Initiation**: Admin uploads menu data via API (CSV/structured format)
2. **Job Processing**: System processes import asynchronously, returns job ID
3. **Status Polling**: Admin monitors job progress via job ID
4. **Completion Handling**: System applies imported data or reports validation errors

### Alt2 Bulk Management
1. **Week Selection**: Admin selects target week/year for Alt2 configuration
2. **Department Scope**: Admin chooses specific departments or site-wide application
3. **Bulk Toggle**: Admin enables/disables Alt2 across selected scope
4. **Conflict Resolution**: System handles scheduling conflicts with existing data

### Statistics & Reporting
1. **Data Aggregation**: System computes weekly/department statistics
2. **Role-Based Access**: Admin/Editor can view stats; Viewer cannot access Admin module
3. **Time Range Filtering**: Admin filters statistics by year/week/department
4. **Export Capabilities**: Admin exports aggregated data for external analysis

## RBAC Matrix

| Operation | Admin | Editor (Staff) | Viewer |
|-----------|-------|----------------|---------|
| **Sites** |
| POST /api/admin/sites | ✅ | ❌ | ❌ |
| **Departments** |
| POST /api/admin/departments | ✅ | ❌ | ❌ |
| PUT /api/admin/departments/{id} | ✅ | ❌ | ❌ |
| PUT /api/admin/departments/{id}/notes | ✅ | ❌ | ❌ |
| PUT /api/admin/departments/{id}/diet-defaults | ✅ | ❌ | ❌ |
| **Menu Import** |
| POST /api/admin/menu-import | ✅ | ❌ | ❌ |
| GET /api/admin/menu-import/{job_id} | ✅ | ✅ | ❌ |
| **Bulk Operations** |
| PUT /api/admin/alt2 | ✅ | ❌ | ❌ |
| **Statistics** |
| GET /api/admin/stats | ✅ | ✅ | ❌ |

### Role Definitions
- **Admin**: Full write access to all admin functions
- **Editor (Staff)**: Read-only access to statistics and job monitoring  
- **Viewer**: No access to Admin module (403 Forbidden)

## ETag & Concurrency Examples

### Department Updates (Optimistic Concurrency)
```http
# Initial GET to retrieve current state
GET /api/admin/departments/123
Response:
ETag: W/"admin:dept:123:v42"
{ "id": 123, "name": "Kitchen Alpha", "default_attendance": 50, "notes": "..." }

# Update with If-Match header
PUT /api/admin/departments/123
If-Match: W/"admin:dept:123:v42"
{ "name": "Kitchen Alpha Updated", "default_attendance": 55 }

# Success response
200 OK
ETag: W/"admin:dept:123:v43"
{ "id": 123, "name": "Kitchen Alpha Updated", "default_attendance": 55 }

# Conflict scenario (stale data)
PUT /api/admin/departments/123
If-Match: W/"admin:dept:123:v41"  // Outdated ETag

# Error response (RFC7807)
412 Precondition Failed
Content-Type: application/problem+json
{
  "type": "https://tools.ietf.org/rfc7231#section-6.5.12",
  "title": "Precondition Failed", 
  "status": 412,
  "detail": "Resource has been modified since last read",
  "instance": "/api/admin/departments/123",
  "request_id": "uuid-here",
  "current_etag": "W/\"admin:dept:123:v43\""
}
```

### Diet Defaults Updates
```http
# Diet defaults follow similar pattern
PUT /api/admin/departments/123/diet-defaults
If-Match: W/"admin:dept:123:diet:v15"
{ "vegetarian": 12, "vegan": 3, "gluten_free": 8 }

# ETag format: admin:dept:{id}:diet:v{version}
```

### Alt2 Bulk Operations
```http
# Bulk Alt2 toggle with week-level ETag
PUT /api/admin/alt2
If-Match: W/"admin:alt2:week:2025:45:v7"
{
  "year": 2025,
  "week": 45, 
  "department_ids": [123, 124, 125],
  "enabled": true
}

# ETag format: admin:alt2:week:{year}:{week}:v{version}
```

### Statistics (Read-Only, Caching)
```http
GET /api/admin/stats?year=2025&week=45
Response:
ETag: W/"admin:stats:y2025:w45:v0"
Cache-Control: private, max-age=0, must-revalidate

# Conditional GET for caching
GET /api/admin/stats?year=2025&week=45
If-None-Match: W/"admin:stats:y2025:w45:v0"
Response: 304 Not Modified
```

## Feature Flag Integration

The Admin module is gated behind the feature flag `ff.admin.enabled`:

- **Enabled**: All admin endpoints are accessible (subject to RBAC)
- **Disabled**: All admin endpoints return 404 Not Found with ProblemDetails

```http
# Feature flag disabled
GET /api/admin/stats
Response: 404 Not Found
Content-Type: application/problem+json
{
  "type": "https://tools.ietf.org/rfc7231#section-6.5.4",
  "title": "Not Found",
  "status": 404, 
  "detail": "Admin module is not enabled",
  "instance": "/api/admin/stats",
  "request_id": "uuid-here"
}
```

## OpenAPI Integration

The Admin API spec is authored as a separate part at `openapi/parts/admin.yml` and is merged into the live `/openapi.json` at runtime via the parts loader.

- Default behavior: merged (env `OPENAPI_INCLUDE_PARTS` defaults to `true`).
- Disable merge by setting `OPENAPI_INCLUDE_PARTS=0` (or `false`/`no`).

This keeps the main spec lean while allowing modular evolution of the Admin contract.

## i18n Keys Specification

All user-facing strings use internationalization keys (no hardcoded text):

### Admin UI Labels
```yaml
admin.nav.title: "Administration"
admin.nav.sites: "Sites"  
admin.nav.departments: "Departments"
admin.nav.diet_types: "Dietary Types"
admin.nav.menu_import: "Menu Import"
admin.nav.alt2_bulk: "Alt2 Bulk Operations"
admin.nav.statistics: "Statistics"

admin.sites.create_title: "Create New Site"
admin.sites.edit_title: "Edit Site"
admin.sites.delete_confirm: "Are you sure you want to delete this site?"

admin.departments.create_title: "Create Department"
admin.departments.edit_title: "Edit Department" 
admin.departments.notes_title: "Department Notes"
admin.departments.diet_defaults_title: "Dietary Defaults"
admin.departments.default_attendance: "Default Attendance"

admin.menu_import.upload_title: "Upload Menu Data"
admin.menu_import.job_status: "Import Status"
admin.menu_import.processing: "Processing..."
admin.menu_import.completed: "Import Completed"
admin.menu_import.failed: "Import Failed"

admin.alt2.bulk_title: "Bulk Alt2 Configuration"
admin.alt2.week_selection: "Select Week"
admin.alt2.department_selection: "Select Departments"
admin.alt2.enable_alt2: "Enable Alt2"
admin.alt2.disable_alt2: "Disable Alt2"

admin.stats.title: "System Statistics"
admin.stats.filters: "Filters"
admin.stats.year_label: "Year"
admin.stats.week_label: "Week" 
admin.stats.department_label: "Department"
admin.stats.export_csv: "Export CSV"
admin.stats.export_xlsx: "Export XLSX"
```

### Error Messages
```yaml
admin.errors.insufficient_permissions: "Insufficient permissions for this operation"
admin.errors.feature_disabled: "Admin module is not enabled"
admin.errors.resource_modified: "Resource has been modified since last read"
admin.errors.validation_failed: "Validation failed"
admin.errors.import_job_not_found: "Import job not found"
admin.errors.invalid_week_range: "Week must be between 1 and 53"
admin.errors.department_not_found: "Department not found"
admin.errors.site_not_found: "Site not found"
```

### Success Messages  
```yaml
admin.success.site_created: "Site created successfully"
admin.success.department_updated: "Department updated successfully"
admin.success.diet_defaults_saved: "Dietary defaults saved"
admin.success.import_started: "Menu import started"
admin.success.alt2_bulk_applied: "Bulk Alt2 configuration applied"
```

## Implementation Notes

### Phase A (Current)
- Feature flag gating and RBAC enforcement
- GET /api/admin/stats with minimal payload and ETag
- All write endpoints return 501 Not Implemented
- Comprehensive OpenAPI specification
- Static UI prototypes with data-* attributes

### Phase B (Future)
- Full persistence layer with repo/service pattern
- ETag versioning with database triggers (Postgres) and fallback (SQLite)
- Asynchronous menu import with job queue
- Complete statistics aggregation reusing Weekview/Report logic
- Interactive UI components with form validation

### Testing Strategy
- Feature flag behavior (enabled/disabled)
- RBAC enforcement across all endpoints
- ETag validation and 412 responses  
- Week range validation (1-53)
- ProblemDetails format compliance
- OpenAPI schema presence and correctness