from django.db import models
from patients.models import Patient
# Create your models here.
class Payment(models.Model):
    """
    To'lov modelini ifodalaydi.
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Naqd pul'),
        ('card', 'Karta'),
        ('online', 'Onlayn to\'lov'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='payments', verbose_name='Bemor')
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='Umumiy xarajat')
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='To\'langan summa')
    debt = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='Qarz', editable=False)
    payment_date = models.DateField(auto_now_add=True, verbose_name='To\'lov sanasi')
    payment_method = models.CharField(max_length=18, choices=PAYMENT_METHOD_CHOICES, verbose_name='To\'lov usuli')
    def save(self, *args, **kwargs):
        self.debt = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient.full_name} - {self.paid_amount} {self.payment_method}"

    class Meta:
        verbose_name = 'To\'lov'
        verbose_name_plural = 'To\'lovlar'
        ordering = ['-payment_date']