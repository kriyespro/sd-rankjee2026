"""Shared realistic Indian parent testimonials for tutor profiles."""

from __future__ import annotations

# (author_name, author_label_template, comment_template, rating)
# Templates may use {subjects}, {city}, {area}, {tutor}, {fee}
TESTIMONIAL_POOL = [
    (
        'Sunita M.',
        'Parent · Class {grade} CBSE',
        'Sir/Madam explains concepts patiently. My child\'s marks in {subjects} improved within 2 months. Regular homework and WhatsApp updates are very helpful.',
        5,
    ),
    (
        'Rajesh K.',
        'Parent · Class {grade}',
        'We tried 2 tutors before. {tutor} is punctual, clear, and focuses on weak topics. Demo class convinced us immediately.',
        5,
    ),
    (
        'Anjali P.',
        'Mother · {city}',
        'Good teaching style for board exams. Notes are neat and monthly progress report keeps us informed. Fee of {fee} is fair for the quality.',
        5,
    ),
    (
        'Vikram S.',
        'Parent · Class {grade} ICSE',
        'My daughter was scared of {subjects}. Now she attempts questions confidently. Highly recommend for home tuition in {area}.',
        5,
    ),
    (
        'Meena D.',
        'Parent · Class {grade}',
        'Punctual and professional. Classes are structured — revision + practice + doubt clearing. We renewed for another term.',
        4,
    ),
    (
        'Suresh R.',
        'Father · {city}',
        'Online + home hybrid option worked well for us. {tutor} adjusts timing around school tests. Very cooperative.',
        5,
    ),
    (
        'Kavita N.',
        'Parent · Class {grade} CBSE',
        'Clear explanation in simple language (Hindi/English mix). Child enjoys the sessions. Would recommend to neighbours.',
        5,
    ),
    (
        'Amit B.',
        'Parent · JEE/NEET foundation',
        'Strong fundamentals for {subjects}. Weekly tests helped us track improvement. Worth the monthly fee.',
        5,
    ),
    (
        'Pooja T.',
        'Mother · Class {grade}',
        'After joining, homework completion improved a lot. Tutor is polite with parents and firm with studies — perfect balance.',
        4,
    ),
    (
        'Deepak J.',
        'Parent · {area}, {city}',
        'Found {tutor} on RankJee. Demo was free and useful. Now attending thrice a week. Happy with results so far.',
        5,
    ),
    (
        'Nisha G.',
        'Parent · Class {grade}',
        'Explains with examples from daily life. My son finally understands chapters he used to skip. Thank you!',
        5,
    ),
    (
        'Ramesh V.',
        'Father · Class {grade} State Board',
        'Reliable tutor. Comes on time, finishes syllabus before exams, and shares past papers. Good experience.',
        4,
    ),
]


def build_testimonials_for_tutor(tutor, count: int = 4) -> list[dict]:
    """Return dicts ready for TutorTestimonial.objects.create (no DB write)."""
    subjects = (tutor.subjects or 'studies').split(',')[0].strip() or 'studies'
    city = tutor.city or 'the city'
    area = tutor.area or city
    fee = tutor.fee_label or '₹6,500/mo'
    grade = max(tutor.teaches_from or 8, min(tutor.teaches_to or 10, 10))
    # Stable pick based on tutor id so re-seed is consistent
    start = (tutor.pk or 1) % len(TESTIMONIAL_POOL)
    out = []
    for i in range(count):
        name, label_t, comment_t, rating = TESTIMONIAL_POOL[(start + i) % len(TESTIMONIAL_POOL)]
        ctx = {
            'subjects': subjects,
            'city': city,
            'area': area,
            'tutor': tutor.display_name.split()[0] if tutor.display_name else 'the tutor',
            'fee': fee,
            'grade': grade,
        }
        # Soften "Sir/Madam" based on first name heuristic (simple)
        first = (tutor.display_name or '').split()[0]
        comment = comment_t.format(**ctx)
        if 'Sir/Madam' in comment:
            # Common Indian female first names → Madam, else Sir
            female = {
                'Priya', 'Sneha', 'Ananya', 'Kavita', 'Meera', 'Neha', 'Pooja', 'Divya',
                'Anjali', 'Shreya', 'Tanvi', 'Isha', 'Nidhi', 'Swati', 'Richa', 'Pallavi',
                'Sonal', 'Komal', 'Ayesha', 'Lakshmi', 'Sunita', 'Jyoti', 'Rekha', 'Bhavna',
                'Chitra', 'Hema', 'Kirti', 'Madhuri', 'Parul', 'Sarita', 'Vandana', 'Zoya',
                'Bharti', 'Devika', 'Esha', 'Gayatri', 'Indira', 'Jaya', 'Lata', 'Naina',
                'Radhika', 'Fatima', 'Geeta', 'Riya', 'Diya', 'Ira',
            }
            honorific = 'Madam' if first in female else 'Sir'
            comment = comment.replace('Sir/Madam', honorific)
        out.append(
            {
                'author_name': name,
                'author_label': label_t.format(**ctx),
                'rating': rating,
                'comment': comment,
                'is_published': True,
            }
        )
    return out
