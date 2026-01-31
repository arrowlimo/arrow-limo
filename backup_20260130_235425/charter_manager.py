"""
Charter Management Functions: Lock, Unlock, Cancel, Delete Charges
Wrapper around database procedures with mandatory business key (reserve_number)
"""

import psycopg2


class CharterManager:
    """Management operations for charters: lock, unlock, cancel, delete charges"""
    
    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.db = db_connection
    
    def lock_charter(self, reserve_number):
        """Lock a charter to prevent editing"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM lock_charter(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                success, message = result
                return success, message
            return False, "No response from database"
        
        except Exception as e:
            return False, f"Error locking charter: {str(e)}"
    
    def unlock_charter(self, reserve_number):
        """Unlock a charter to allow editing"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM unlock_charter(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                success, message = result
                return success, message
            return False, "No response from database"
        
        except Exception as e:
            return False, f"Error unlocking charter: {str(e)}"
    
    def cancel_charter(self, reserve_number):
        """Cancel charter and delete $0 charges"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM cancel_charter(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                success, message, deleted_count = result
                return success, message, deleted_count
            return False, "No response from database", 0
        
        except Exception as e:
            return False, f"Error cancelling charter: {str(e)}", 0
    
    def delete_charge(self, reserve_number, charge_id, reason=None):
        """Delete a specific charge from a charter"""
        try:
            cur = self.db.cursor()
            cur.execute(
                "SELECT * FROM delete_charge(%s, %s, %s)",
                (reserve_number, charge_id, reason)
            )
            result = cur.fetchone()
            cur.close()
            
            if result:
                success, message, deleted_amount = result
                return success, message, deleted_amount
            return False, "No response from database", 0
        
        except Exception as e:
            return False, f"Error deleting charge: {str(e)}", 0
    
    def get_lock_status(self, reserve_number):
        """Check if charter is locked"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM get_charter_lock_status(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                is_locked, status = result
                return is_locked, status
            return False, "Unknown"
        
        except Exception as e:
            return False, f"Error checking lock status: {str(e)}"
    
    def get_balance(self, reserve_number):
        """Get charter balance (charges - payments)"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM get_charter_balance(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                total_charges, total_payments, balance_due = result
                return {
                    'total_charges': float(total_charges or 0),
                    'total_payments': float(total_payments or 0),
                    'balance_due': float(balance_due or 0)
                }
            return None
        
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            return None
    
    def record_nfd(self, reserve_number):
        """Record No Funds Deposit (NFD) charge of $25"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT * FROM record_nfd_charge(%s)", (reserve_number,))
            result = cur.fetchone()
            cur.close()
            
            if result:
                success, message, charge_id = result
                return success, message, charge_id
            return False, "No response from database", None
        
        except Exception as e:
            return False, f"Error recording NFD: {str(e)}", None
