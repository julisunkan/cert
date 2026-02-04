# Certificate Generator

## Overview

A professional certificate generation web application built with Python Flask that creates print-ready PDF certificates for courses, churches, schools, events, and trainings. The application supports single and bulk certificate generation with CSV upload, ZIP export, QR code verification, digital signatures, issuer logo upload, certificate serial numbers, and anti-forgery protection.

Key capabilities:
- 20 pre-loaded professional certificate templates across 4 categories (Education, Church & Religious, Events & Community, Business & Training)
- Single certificate generation with customizable fields
- Bulk generation via CSV upload with ZIP download
- QR code-based certificate verification system
- Digital signature and logo upload support
- Unique serial numbers and security IDs for anti-forgery

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Framework**: Flask (Python web framework)
- **Rationale**: Lightweight, minimal boilerplate, well-suited for this scope of application
- **No authentication required**: All users have full access without login/registration

### Data Storage
- **Database**: SQLite with raw SQL (no ORM)
- **Schema**: Two main tables:
  - `templates`: Stores certificate template definitions with JSON configuration for layout
  - `certificates`: Stores issued certificates with serial numbers, recipient info, and verification data
- **Template Configuration**: Layout stored as JSON controlling text positions, fonts, colors, and styling

### PDF Generation
- **Library**: ReportLab
- **Features**: Supports both portrait and landscape orientations, A4 page size, embedded images (logos, signatures), QR codes
- **QR Codes**: Generated using the `qrcode` library, embedded in PDFs for verification

### File Handling
- **Bulk Export**: Uses Python's built-in `zipfile` for packaging multiple PDFs
- **CSV Processing**: Built-in `csv` module for bulk recipient data
- **Uploads**: Flask's file upload handling for logos and signatures, stored in `static/` folder

### Security & Verification
- **Certificate IDs**: Generated using `uuid` for unique identification
- **Serial Numbers**: Unique identifiers for each certificate
- **Hash Generation**: Uses `hashlib` for security checksums
- **Verification Endpoint**: Public endpoint to verify certificate authenticity via serial number or ID

### Template Categories
Templates are organized into 4 categories with 5 templates each:
1. Education
2. Church & Religious
3. Events & Community
4. Business & Training

### Routes Structure
- `/` - Homepage with template gallery
- `/generate/<template_id>` - Single certificate generation form
- `/bulk/<template_id>` - Bulk generation with CSV upload
- `/verify/<id>` - Certificate verification page
- `/admin/templates` - Admin panel for template management

## External Dependencies

### Python Packages
- **Flask**: Web framework and routing
- **ReportLab**: PDF generation with precise layout control
- **qrcode**: QR code generation for certificate verification
- **Pillow** (implicit via qrcode): Image processing for QR codes

### Frontend Resources
- **Water.css** (CDN): Minimal CSS framework for styling without custom CSS complexity

### Built-in Python Modules
- `sqlite3`: Database operations
- `csv`: CSV file parsing for bulk generation
- `zipfile`: ZIP archive creation for bulk downloads
- `uuid`: Unique identifier generation
- `hashlib`: Cryptographic hashing for security
- `io.BytesIO`: In-memory file handling for PDF/image streams

### Environment Variables
- `SECRET_KEY`: Flask session security (defaults to 'dev-key-123')
- `ADMIN_SECRET_KEY`: Admin panel access (defaults to 'change-me')

### No External APIs
The application is fully self-contained with no external API dependencies, designed to run entirely on Replit without network requirements beyond serving the web interface.