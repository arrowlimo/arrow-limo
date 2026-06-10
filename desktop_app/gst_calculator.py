"""
GST (Goods and Services Tax) calculation utilities for Alberta.

Alberta has 5% GST included in pricing (tax-included model).
"""



class GSTCalculator:
    """GST calculation utilities (Alberta 5% GST, tax-included)"""

    GST_RATE = 0.05

    @staticmethod
    def calculate_gst(gross_amount: float) -> tuple[float, float]:
        """
        Calculate GST from tax-included amount.
        GST is INCLUDED in the gross amount (not added).

        Args:
            gross_amount: Total amount including GST

        Returns:
            Tuple of (gst_amount, net_amount)

        Example:
            $682.50 total INCLUDES $32.50 GST
            gst, net = calculate_gst(682.50)  # returns (32.50, 650.00)
        """
        gst_amount = gross_amount * GSTCalculator.GST_RATE / \
            (1 + GSTCalculator.GST_RATE)
        net_amount = gross_amount - gst_amount
        return (round(gst_amount, 2), round(net_amount, 2))

    @staticmethod
    def add_gst(net_amount: float) -> float:
        """
        Calculate gross amount from net (adds GST).

        Args:
            net_amount: Amount before GST

        Returns:
            Total amount including GST
        """
        return round(net_amount * (1 + GSTCalculator.GST_RATE), 2)
