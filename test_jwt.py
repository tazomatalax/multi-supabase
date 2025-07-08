#!/usr/bin/env python3
"""
Test script to validate JWT token generation for Supabase.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from setup import generate_secrets, validate_jwt_tokens
import jwt

def test_jwt_generation():
    """Test JWT token generation and validation."""
    print("Testing JWT token generation...")
    
    # Generate secrets
    secrets = generate_secrets()
    
    # Print generated tokens
    print(f"JWT Secret: {secrets['jwt_secret']}")
    print(f"Anon Key: {secrets['anon_key']}")
    print(f"Service Role Key: {secrets['service_role_key']}")
    
    # Validate tokens
    try:
        validate_jwt_tokens(secrets)
        print("✅ JWT token validation successful!")
    except Exception as e:
        print(f"❌ JWT token validation failed: {e}")
        return False
    
    # Decode and verify token contents
    try:
        anon_decoded = jwt.decode(secrets['anon_key'], secrets['jwt_secret'], algorithms=['HS256'])
        service_decoded = jwt.decode(secrets['service_role_key'], secrets['jwt_secret'], algorithms=['HS256'])
        
        print(f"Anon token payload: {anon_decoded}")
        print(f"Service token payload: {service_decoded}")
        
        # Verify roles
        assert anon_decoded['role'] == 'anon'
        assert service_decoded['role'] == 'service_role'
        
        print("✅ Token roles verified!")
        
    except Exception as e:
        print(f"❌ Token decoding failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_jwt_generation()
    sys.exit(0 if success else 1)
