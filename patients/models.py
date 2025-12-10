from django.db import models
from datetime import date
# Create your models here.

class Patient(models.Model):
    """
    Bemor modelini ifodalaydi.
    """
    GENDER_CHOICES = [
        ('M', 'Erkak'),
        ('F', 'Ayol'),
        ('O', 'Boshqa'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Faol'),
        ('inactive', 'Nofaol'),
        ('pending', 'Kutilmoqda'),
    ]

    full_name = models.CharField(max_length=255, verbose_name='To\'liq ismi')
    date_of_birth = models.DateField(verbose_name='Tug\'ilgan yil')
    age = models.PositiveIntegerField(verbose_name='Yosh', editable=False)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='Jins')
    phone_number = models.CharField(max_length=15, unique=True, verbose_name='Telefon')
    visit_date = models.DateTimeField(verbose_name='Kelish Vaqti', auto_now_add=True)
    last_coming = models.DateField(verbose_name='So\'nggi Davolanish', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name='Holat', default='active')
    notes = models.TextField(verbose_name='Eslatmalar', blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.date_of_birth:
            today = date.today()
            self.age = today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name}"
    
    class Meta:
        verbose_name = 'Bemor'
        verbose_name_plural = 'Bemorlar'
        ordering = ['-last_coming']

class MedicalRecord(models.Model):
    """
    Bemorning tibbiy yozuvlarini ifodalaydi.
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records', verbose_name='Bemor')
    record_date = models.DateField(verbose_name='Yozuv sanasi')
    description = models.TextField(verbose_name='Tibbiy yozuv')

    def __str__(self):
        return f"{self.patient.full_name} - {self.record_date}"
    
    class Meta:
        verbose_name = 'Tibbiy yozuv'
        verbose_name_plural = 'Tibbiy yozuvlar'
        ordering = ['-record_date']

class MedicalAssessment(models.Model):
    """
    Bemorning tibbiy baholashlarini ifodalaydi.
    """
    CONDITION = [
        ('caries', 'Karies'),
        ('periodontitis', 'Periodontit'),
        ('gingivitis', 'Gingivit'),
        ('extraction', 'Tish olish'),
        ('pulpitis', 'Pulpit'),
        ('parodontitis', 'Parodontit'),
        ('stomatitis', 'Stomatit'),
        ('xray', 'Rentgen'),
        ('other', 'Boshqa'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_assessments', verbose_name='Bemor')
    assessment_date = models.DateField(verbose_name='Baholash sanasi')
    patient_condition = models.CharField(max_length=255, choices=CONDITION, verbose_name='Bemor holati', blank=True, null=True)
    assessment = models.TextField(verbose_name='Tibbiy baholash')
    rengen_image = models.ImageField(upload_to='rengen_images/', verbose_name='Rentgen rasmi', blank=True, null=True)
    additional_notes = models.TextField(verbose_name='Qo\'shimcha eslatmalar', blank=True, null=True)
    treatment_plan = models.TextField(verbose_name='Davolash rejasi', blank=True, null=True)
    total_mhshb = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Jami MHSHB', default=0)
    mhshb_checkup = models.TextField(verbose_name='MHSHB prof ko\'rik', blank=True, null=True)
    diagnosis = models.TextField(verbose_name='Tashxis', blank=True, null=True)


    def __str__(self):
        return f"{self.patient.full_name} - {self.assessment_date}"
    
    class Meta:
        verbose_name = 'Tibbiy baholash'
        verbose_name_plural = 'Tibbiy baholashlar'
        ordering = ['-assessment_date']