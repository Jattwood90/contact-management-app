#!/usr/bin/env python3

"""
TODO - add in responses from SMARTY API as there's more info there that can be used as a report.

json response from valid address:

[{'input_index': 0, 'candidate_index': 0, 'delivery_line_1': '119 Burnet Way', 
'last_line': 'Charlottesville VA 22902-6190', 'delivery_point_barcode': '229026190199', 
'components': {'primary_number': '119', 'street_name': 'Burnet', 'street_suffix': 'Way', 'city_name': 
'Charlottesville', 'default_city_name': 'Charlottesville', 'state_abbreviation': 'VA', 
'zipcode': '22902', 'plus4_code': '6190', 'delivery_point': '19', 
'delivery_point_check_digit': '9'}, 
'metadata': {'record_type': 'S', 'zip_type': 'Standard', 
'county_fips': '51540', 'county_name': 'Charlottesville City', 
'carrier_route': 'C001', 'congressional_district': '05', 'rdi': 
'Residential', 'elot_sequence': '0191', 'elot_sort': 'A', 'latitude': 38.02388, 
'longitude': -78.48779, 'precision': 'Zip9', 'time_zone': 'Eastern', 
'utc_offset': -5, 'dst': True}, 'analysis': {'dpv_match_code': 'Y', 'dpv_footnotes': 'AABB', 
'dpv_cmra': 'N', 'dpv_vacant': 'N', 'dpv_no_stat': 'N', 'active': 'Y'}}]

"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import psycopg2
import requests
import json
import logging
import random
from jinja2 import Template
from datetime import datetime
from functools import wraps


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config.update(
    DB_HOST=os.getenv('DB_HOST', 'postgres_db'),
    DB_PORT=os.getenv('DB_PORT', '5432'),
    DB_NAME=os.getenv('POSTGRES_DB', 'postgres'),
    DB_USERNAME=os.getenv('DB_USERNAME', 'postgres'),
    POSTGRES_PASSWORD=os.getenv('POSTGRES_PASSWORD', None),
    SMARTY_AUTH_ID=os.getenv('SMARTY_AUTH_ID', None),
    SMARTY_AUTH_TOKEN=os.getenv('SMARTY_AUTH_TOKEN', None),
    TEMPLATE_STYLE=os.getenv('TEMPLATE_STYLE', 'random'),
    TEMPLATES_DIR=os.getenv('TEMPLATES_DIR', 'templates'),
    OUTPUT_DIR=os.getenv('OUTPUT_DIR', 'static/generated')
)

def handle_db_errors(f):
    """Decorator to handle database connection errors"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            return jsonify({'error': 'Database connection failed'}), 500
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function

def validate_address_smarty(address, city, state, zipcode, auth_id=None, auth_token=None):
    """Validate address using SmartyStreets API"""
    if not auth_id or not auth_token:
        logger.warning("SmartyStreets credentials not provided, skipping validation")
        return "Not Validated"

    try:
        # could probably make this more dynamic/hidden
        url = "https://us-street.api.smartystreets.com/street-address"
        params = {
            'auth-id': auth_id,
            'auth-token': auth_token,
            'street': address,
            'city': city,
            'state': state,
            'zipcode': zipcode
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data
            else:
                return False
        else:
            logger.warning(f"SmartyStreets API error: {response.status_code}")
            return "API Error"

    except requests.RequestException as e:
        logger.error(f"Address validation failed: {e}")
        return "Validation Failed"

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            database=app.config['DB_NAME'],
            user=app.config['DB_USERNAME'],
            password=app.config['POSTGRES_PASSWORD']
        )
        return conn
    except psycopg2.Error as e:
        logger.critical(f"Database connection failed: {e}")
        raise

def fetch_contacts():
    """Fetch all contacts from database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, first_name, last_name, address, city, state, zipcode, country, valid 
            FROM public.contacts 
            ORDER BY last_name, first_name
        """)

        columns = [desc[0] for desc in cursor.description]
        contacts = []
        for row in cursor.fetchall():
            contact = dict(zip(columns, row))
            contacts.append(contact)

        cursor.close()
        logger.info(f"Fetched {len(contacts)} contacts from database")
        return contacts

    finally:
        conn.close()

def update_validation_status(contact_id, validation_status):
    """Update validation status in database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contacts SET valid = %s WHERE id = %s",
            (validation_status, contact_id)
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()

def get_template_files():
    """Return mapping of template styles to filenames"""
    return {
        "modern": "modern_template.html",
        "dark": "dark_template.html",
        "neon": "neon_template.html",
        "retro": "retro_template.html"
    }

def select_template_style(template_style="random"):
    """Select template style, handling random selection"""
    template_files = get_template_files()

    if template_style == "random":
        selected_style = random.choice(list(template_files.keys()))
        logger.info(f"Randomly selected template: {selected_style}")
        return selected_style

    return template_style

def load_template(template_style, templates_dir="templates"):
    """Load and return template content from file"""
    template_files = get_template_files()
    template_filename = template_files.get(template_style, template_files["modern"])
    template_path = os.path.join(templates_dir, template_filename)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

def get_validation_attributes(valid_status):
    """Return CSS class, badge class, and validation text based on status"""
    if valid_status == 'valid':
        return 'valid', 'valid-badge', 'Valid Address'
    elif valid_status == 'invalid':
        return 'invalid', 'invalid-badge', 'Invalid Address'
    else:
        return 'not-validated', 'not-validated-badge', 'Not Validated'

def prepare_contact_data(contacts):
    """Add validation styling attributes to contact data"""
    for contact in contacts:
        valid_status = contact.get('valid', '')
        css_class, badge_class, validation_text = get_validation_attributes(valid_status)

        contact['css_class'] = css_class
        contact['badge_class'] = badge_class
        contact['validation_text'] = validation_text

    return contacts

def prepare_template_data(contacts):
    """Prepare all data needed for template rendering"""
    prepared_contacts = prepare_contact_data(contacts)

    return {
        'contacts': prepared_contacts,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def render_custom_template(template_content, template_data):
    """Render Jinja template with provided data"""
    template = Template(template_content)
    return template.render(**template_data)

def generate_html_file(contacts, template_style="random", output_filename="index.html"):
    """Generate HTML file from contacts data using external Jinja templates"""
    # Ensure output directory exists
    os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)
    
    # Select template style
    selected_style = select_template_style(template_style)
    
    # Load template content
    template_content = load_template(selected_style, app.config['TEMPLATES_DIR'])
    
    # Prepare template data
    template_data = prepare_template_data(contacts)
    
    # Render template
    html_content = render_custom_template(template_content, template_data)
    
    # Write to file
    output_path = os.path.join(app.config['OUTPUT_DIR'], output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"HTML file generated: {output_path}")
    return output_path, selected_style

# Flask Routes

@app.route('/')
def index():
    """Main page showing contacts"""
    return render_template('index.html')

@app.route('/api/contacts')
@handle_db_errors
def api_contacts():
    """API endpoint to get all contacts"""
    contacts = fetch_contacts()
    return jsonify({
        'contacts': contacts,
        'count': len(contacts),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/contacts/<int:contact_id>')
@handle_db_errors
def api_contact_detail(contact_id):
    """API endpoint to get specific contact"""
    contacts = fetch_contacts()
    contact = next((c for c in contacts if c['id'] == contact_id), None)
    
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404
    
    return jsonify(contact)

@app.route('/api/validate', methods=['POST'])
@handle_db_errors
def api_validate_addresses():
    """API endpoint to validate all addresses"""
    contacts = fetch_contacts()
    
    if not contacts:
        return jsonify({'error': 'No contacts found'}), 404
    
    validated_contacts = []
    
    for contact in contacts:
        validation_result = validate_address_smarty(
            contact['address'],
            contact['city'],
            contact['state'],
            contact['zipcode'],
            app.config['SMARTY_AUTH_ID'],
            app.config['SMARTY_AUTH_TOKEN']
        )
        
        # Update database
        update_validation_status(contact['id'], validation_result)
        
        # Update contact data
        contact['valid'] = validation_result
        validated_contacts.append(contact)
        
        logger.info(f"Validated {contact['first_name']} {contact['last_name']}: {validation_result}")
    
    return jsonify({
        'message': 'Address validation completed',
        'contacts': validated_contacts,
        'count': len(validated_contacts)
    })

@app.route('/api/validate/<int:contact_id>', methods=['POST'])
@handle_db_errors
def api_validate_single_address(contact_id):
    """API endpoint to validate single address"""
    contacts = fetch_contacts()
    contact = next((c for c in contacts if c['id'] == contact_id), None)
    
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404
    
    validation_result = validate_address_smarty(
        contact['address'],
        contact['city'],
        contact['state'],
        contact['zipcode'],
        app.config['SMARTY_AUTH_ID'],
        app.config['SMARTY_AUTH_TOKEN']
    )
    
    # Update database
    update_validation_status(contact_id, validation_result)
    contact['valid'] = validation_result
    
    logger.info(f"Validated {contact['first_name']} {contact['last_name']}: {validation_result}")
    
    return jsonify({
        'message': 'Address validation completed',
        'contact': contact
    })

@app.route('/api/generate', methods=['POST'])
@handle_db_errors
def api_generate_html():
    """API endpoint to generate HTML file"""
    data = request.get_json() or {}
    template_style = data.get('template_style', app.config['TEMPLATE_STYLE'])
    output_filename = data.get('output_filename', 'index.html')
    
    contacts = fetch_contacts()
    
    if not contacts:
        return jsonify({'error': 'No contacts found'}), 404
    
    try:
        output_path, selected_style = generate_html_file(contacts, template_style, output_filename)
        
        return jsonify({
            'message': 'HTML file generated successfully',
            'output_path': output_path,
            'template_style': selected_style,
            'contacts_count': len(contacts),
            'download_url': f'/download/{output_filename}'
        })
        
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated HTML files"""
    try:
        return send_from_directory(app.config['OUTPUT_DIR'], filename)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/templates')
def api_template_styles():
    """API endpoint to get available template styles"""
    return jsonify({
        'template_styles': list(get_template_files().keys()),
        'default': app.config['TEMPLATE_STYLE']
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db_connection()
        conn.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        'status': 'healthy' if db_status == "healthy" else 'unhealthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/config')
def api_config():
    """API endpoint to get current configuration (non-sensitive)"""
    return jsonify({
        'template_style': app.config['TEMPLATE_STYLE'],
        'templates_dir': app.config['TEMPLATES_DIR'],
        'output_dir': app.config['OUTPUT_DIR'],
        'smarty_configured': bool(app.config['SMARTY_AUTH_ID'] and app.config['SMARTY_AUTH_TOKEN'])
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)
    
    # Run the Flask app
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 3000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    
    logger.info(f"Starting Flask app on {host}:{port} (debug={debug_mode})")
    app.run(host=host, port=port, debug=debug_mode)