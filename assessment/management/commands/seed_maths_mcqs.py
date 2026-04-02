import json
from django.core.management.base import BaseCommand
from assessment.models import SkillPath, Skill, Question, QuestionSet
from django.db import transaction

class Command(BaseCommand):
    help = "Seeds the database with 100 high-quality Class 11 Maths MCQs"

    def handle(self, *args, **kwargs):
        # 1. Identify Target SkillPath and Skill
        path_name = "Class 11th"
        skill_name = "Maths"
        
        sp = SkillPath.objects.filter(name__icontains=path_name).first()
        if not sp:
            self.stdout.write(self.style.ERROR(f"SkillPath '{path_name}' not found. Creating it..."))
            sp = SkillPath.objects.create(name="Class 11th (Level 1)", level_order=1)
        
        skill = Skill.objects.filter(name__icontains=skill_name, path=sp).first()
        if not skill:
            self.stdout.write(self.style.ERROR(f"Skill '{skill_name}' not found. Creating it..."))
            skill = Skill.objects.create(name="0. Maths", path=sp, order=0)

        # 2. Define 100 High Quality MCQs
        # Structured as: [text, concept_tag, explanation, difficulty, op_a, op_b, op_c, op_d, correct]
        raw_questions = [
            # Sets (1-7)
            ["Which of the following is a null set?", "Sets", "The set of even prime numbers greater than 2 is empty as 2 is the only even prime.", "EASY", "{2}", "{0}", "Set of even prime numbers > 2", "Set of odd natural numbers", "C"],
            ["The power set of the set {a, b} is:", "Sets", "Power set contains all possible subsets including empty and self. 2^2 = 4.", "EASY", "{a, b}", "{{a}, {b}}", "{∅, {a}, {b}, {a, b}}", "{∅, a, b}", "C"],
            ["If n(A) = 3 and n(B) = 6, what is the minimum number of elements in A ∪ B?", "Sets", "Min elements when A ⊆ B, so max(n(A), n(B)) = 6.", "MEDIUM", "3", "6", "9", "0", "B"],
            ["If A ∩ B = A, then:", "Sets", "Intersection being A implies A is a subset of B.", "EASY", "A ⊆ B", "B ⊆ A", "A = ∅", "A = B", "A"],
            ["Representing 'x is a real number and -2 < x ≤ 5' in interval notation:", "Sets", "-2 is excluded (round bracket), 5 is included (square bracket).", "EASY", "(-2, 5]", "[-2, 5)", "(-2, 5)", "[-2, 5]", "A"],
            ["The number of subsets of a set containing n elements is:", "Sets", "Each element has 2 choices: in or out. Total 2^n.", "EASY", "n", "2n", "n^2", "2^n", "D"],
            ["If A = {1, 2, 3, 4} and B = {3, 4, 5, 6}, find A - B:", "Sets", "Elements in A but not in B.", "EASY", "{1, 2}", "{5, 6}", "{3, 4}", "{1, 2, 5, 6}", "A"],

            # Relations & Functions (8-15)
            ["The range of the function f(x) = |x-1| is:", "Functions", "Absolute value is always non-negative.", "EASY", "R", "[0, ∞)", "(0, ∞)", "(-∞, 1]", "B"],
            ["If f(x) = x^2 and g(x) = 2x+1, find fog(0):", "Functions", "g(0) = 1, f(1) = 1^2 = 1.", "EASY", "0", "1", "2", "3", "B"],
            ["The domain of f(x) = 1/√(x-2) is:", "Functions", "x-2 must be strictly greater than 0 for square root in denominator.", "MEDIUM", "x > 2", "x ≥ 2", "x < 2", "x ≠ 2", "A"],
            ["If f(x) = sin x and g(x) = x^2, then gof(x) is:", "Functions", "g(f(x)) = g(sin x) = (sin x)^2.", "EASY", "sin(x^2)", "sin^2 x", "2 sin x", "x^2 sin x", "B"],
            ["A relation R on set A is reflexive if:", "Relations", "Every element relates to itself: (a, a) ∈ R for all a.", "EASY", "(a,b)∈R => (b,a)∈R", "(a,a)∈R for all a", "(a,b)∈R, (b,c)∈R => (a,c)∈R", "None", "B"],
            ["What is the identity function f: R → R?", "Functions", "f(x) = x for all x.", "EASY", "f(x) = 0", "f(x) = 1", "f(x) = x", "f(x) = -x", "C"],
            ["If f(x) = (x-1)/(x+1), find f(1/x):", "Functions", "Substitute 1/x: ((1/x)-1)/((1/x)+1) = (1-x)/(1+x) = -f(x).", "HARD", "f(x)", "-f(x)", "1/f(x)", "None", "B"],
            ["The number of relations from set A={1,2} to B={3,4} is:", "Relations", "Number of relations is 2^(n(A)*n(B)) = 2^4 = 16.", "MEDIUM", "4", "8", "16", "32", "C"],

            # Trigonometry (16-25)
            ["The value of sin(-420°) is:", "Trigonometry", "sin(-420) = -sin(420) = -sin(360+60) = -sin 60 = -√3/2.", "MEDIUM", "√3/2", "-√3/2", "1/2", "-1/2", "B"],
            ["If cos x = -1/2 and x lies in 3rd quadrant, find sin x:", "Trigonometry", "In 3rd quad, sin is negative. sin^2 x = 1 - 1/4 = 3/4. sin x = -√3/2.", "MEDIUM", "√3/2", "-√3/2", "1/2", "-1/2", "B"],
            ["The general solution of tan x = √3 is:", "Trigonometry", "Principal value is π/3. General solution: nπ + π/3.", "MEDIUM", "nπ + π/3", "nπ - π/3", "2nπ + π/3", "nπ + π/6", "A"],
            ["The value of cos 15° is:", "Trigonometry", "cos(45-30) = cos45 cos30 + sin45 sin30 = (√3+1)/(2√2).", "MEDIUM", "(√3-1)/(2√2)", "(√3+1)/(2√2)", "√3/2", "1/√2", "B"],
            ["sin 2x is equal to:", "Trigonometry", "Standard double angle formula.", "EASY", "2 sin x", "sin x cos x", "2 sin x cos x", "cos^2 x - sin^2 x", "C"],
            ["The maximum value of 3 sin x + 4 cos x is:", "Trigonometry", "Max value of a sin x + b cos x is √(a^2+b^2) = √(9+16) = 5.", "MEDIUM", "7", "5", "1", "12", "B"],
            ["In any triangle ABC, a/(sin A) = b/(sin B) = c/(sin C) is called:", "Trigonometry", "Fundamental law of sines.", "EASY", "Cosine Rule", "Sine Rule", "Projection Rule", "Tangent Rule", "B"],
            ["The value of tan(π/8) is:", "Trigonometry", "Using tan(2θ) formula, tan(π/8) = √2 - 1.", "HARD", "√2 - 1", "√2 + 1", "1 - √2", "2 - √2", "A"],
            ["Degree measure of 7π/6 radians is:", "Trigonometry", "(7π/6) * (180/π) = 7 * 30 = 210.", "EASY", "150°", "210°", "240°", "300°", "B"],
            ["Period of function f(x) = sin(3x + 5) is:", "Trigonometry", "Period of sin(ax+b) is 2π/|a|.", "MEDIUM", "2π", "2π/3", "6π", "π/3", "B"],

            # Complex Numbers (26-35)
            ["The value of i^19 is:", "Complex Numbers", "i^19 = i^(16+3) = i^3 = -i.", "EASY", "1", "-1", "i", "-i", "D"],
            ["Modulus of complex number z = 1 + i√3 is:", "Complex Numbers", "|z| = √(1^2 + (√3)^2) = √(1+3) = 2.", "EASY", "1", "√3", "2", "4", "C"],
            ["The conjugate of (2+i)^2 is:", "Complex Numbers", "(2+i)^2 = 4 + 4i - 1 = 3 + 4i. Conjugate is 3 - 4i.", "MEDIUM", "3+4i", "3-4i", "4-3i", "5-i", "B"],
            ["If x + iy = (1+i)/(1-i), then (x,y) is:", "Complex Numbers", "(1+i)^2 / (1-i^2) = 2i/2 = i. So x=0, y=1.", "MEDIUM", "(1,1)", "(0,1)", "(1,0)", "(-1,0)", "B"],
            ["The square roots of -16 are:", "Complex Numbers", "±√(-16) = ±4i.", "EASY", "±4", "±4i", "4i", "-4i", "B"],
            ["Polar form of z = i is:", "Complex Numbers", "r=1, θ=π/2. z = cos(π/2) + i sin(π/2).", "MEDIUM", "cos 0 + i sin 0", "cos π + i sin π", "cos(π/2) + i sin(π/2)", "None", "C"],
            ["Multiciplicative inverse of 4-3i is:", "Complex Numbers", "conj(z)/|z|^2 = (4+3i)/25.", "MEDIUM", "(4+3i)/25", "(4-3i)/25", "4+3i", "4-3i", "A"],
            ["Argument of z = -1 - i is:", "Complex Numbers", "3rd quadrant, -3π/4 or 5π/4. Principal is -3π/4.", "HARD", "π/4", "3π/4", "-3π/4", "5π/4", "C"],
            ["If 1, ω, ω^2 are cube roots of unity, then 1 + ω + ω^2 is:", "Complex Numbers", "Fundamental property of cube roots of unity.", "EASY", "0", "1", "3", "ω", "A"],
            ["Roots of quadratic equation x^2 + 3 = 0 are:", "Quadratic Equations", "x^2 = -3 => x = ±i√3.", "EASY", "±3", "±√3", "±i√3", "None", "C"],

            # Permutations & Combinations (36-45)
            ["Value of 0! is:", "P&C", "By definition, 0! = 1.", "EASY", "0", "1", "Undefined", "Infinite", "B"],
            ["How many 3-digit numbers can be formed from {1,2,3,4,5} if repetition is allowed?", "P&C", "5 * 5 * 5 = 125.", "EASY", "60", "125", "120", "25", "B"],
            ["Value of 5P2 is:", "P&C", "5! / (5-2)! = 5 * 4 = 20.", "EASY", "10", "20", "120", "60", "B"],
            ["Value of 10C8 is:", "P&C", "10C8 = 10C2 = (10*9)/2 = 45.", "EASY", "45", "90", "80", "10", "A"],
            ["If nC8 = nC2, find n:", "P&C", "If nCx = nCy, then x+y=n. So n = 8+2 = 10.", "MEDIUM", "8", "10", "16", "20", "B"],
            ["Number of ways 5 people can sit in a row is:", "P&C", "5! = 120.", "EASY", "5", "10", "20", "120", "D"],
            ["Number of diagonals in a polygon of n sides is:", "P&C", "nC2 - n = n(n-3)/2.", "MEDIUM", "n(n-1)/2", "n(n-3)/2", "n^2", "n!", "B"],
            ["Number of words that can be formed from 'APPLE' is:", "P&C", "5! / 2! (P repeats) = 120/2 = 60.", "MEDIUM", "120", "60", "30", "24", "B"],
            ["In how many ways can a committee of 3 be chosen from 5 men and 2 women if it must contain at least 1 woman?", "P&C", "Total - No woman = 7C3 - 5C3 = 35 - 10 = 25.", "HARD", "25", "35", "10", "21", "A"],
            ["Circular permutations of n distinct objects is:", "P&C", "(n-1)!.", "MEDIUM", "n!", "(n-1)!", "n!/2", "(n-2)!", "B"],

            # Binomial Theorem (46-52)
            ["Number of terms in expansion of (x+y)^n is:", "Binomial", "There are always n+1 terms.", "EASY", "n-1", "n", "n+1", "2n", "C"],
            ["General term T(r+1) in expansion of (a+b)^n is:", "Binomial", "Standard formula nCr a^(n-r) b^r.", "MEDIUM", "nCr a^r b^(n-r)", "nCr a^(n-r) b^r", "nCr a^n b^r", "None", "B"],
            ["Sum of binomial coefficients in (1+x)^n is:", "Binomial", "Put x=1, (1+1)^n = 2^n.", "MEDIUM", "n", "2n", "2^n", "n^2", "C"],
            ["The coefficient of x^5 in (1+x)^10 is:", "Binomial", "10C5.", "MEDIUM", "10C5", "10C4", "10C6", "1", "A"],
            ["Middle term in (x + 1/x)^10 is:", "Binomial", "n=10 is even, middle term is (10/2)+1 = 6th term. T6 = 10C5.", "MEDIUM", "10C4", "10C5", "10C6", "1", "B"],
            ["Term independent of x in (x + 1/x)^2n is:", "Binomial", "(2n)Cn.", "HARD", "nCn", "(2n)Cn", "1", "None", "B"],
            ["The value of 11^3 using binomial theorem:", "Binomial", "(10+1)^3 = 1000 + 300 + 30 + 1 = 1331.", "EASY", "1211", "1331", "1441", "None", "B"],

            # Sequences & Series (53-62)
            ["10th term of AP 2, 5, 8... is:", "Sequences", "a=2, d=3. a10 = 2 + 9*3 = 29.", "EASY", "27", "29", "31", "32", "B"],
            ["Sum of first 10 terms of AP 1, 3, 5... is:", "Sequences", "Sum of first n odd numbers is n^2. 10^2 = 100.", "EASY", "100", "90", "110", "120", "A"],
            ["If a, b, c are in AP, then:", "Sequences", "2b = a + c.", "EASY", "b = a+c", "b^2 = ac", "2b = a+c", "b = (a+c)/3", "C"],
            ["5th term of GP 3, 6, 12... is:", "Sequences", "a=3, r=2. a5 = 3 * 2^4 = 3 * 16 = 48.", "EASY", "24", "48", "96", "192", "B"],
            ["Sum of infinite GP 1, 1/2, 1/4... is:", "Sequences", "a=1, r=1/2. Sum = a/(1-r) = 1/(1/2) = 2.", "MEDIUM", "1", "2", "1.5", "Infinite", "B"],
            ["Geometric Mean of 4 and 16 is:", "Sequences", "GM = √(4*16) = √64 = 8.", "EASY", "8", "10", "12", "6", "A"],
            ["The n-th term of series 1, 3, 6, 10... is:", "Sequences", "Triangular numbers: n(n+1)/2.", "MEDIUM", "n^2", "n(n+1)/2", "2n-1", "n(n-1)/2", "B"],
            ["If AM and GM of two numbers are 10 and 8, the numbers are:", "Sequences", "a+b=20, ab=64. Roots of x^2-20x+64=0 are 16, 4.", "MEDIUM", "16, 4", "12, 8", "15, 5", "None", "A"],
            ["Sum to n terms of 1 + 2 + 3 + ... + n is:", "Sequences", "Standard formula.", "EASY", "n(n+1)/2", "n^2", "n(n-1)/2", "n(n+1)(2n+1)/6", "A"],
            ["Sum of squares of first n natural numbers is:", "Sequences", "Standard formula.", "MEDIUM", "n(n+1)/2", "[n(n+1)/2]^2", "n(n+1)(2n+1)/6", "None", "C"],

            # Straight Lines (63-72)
            ["Distance between (1,2) and (4,6) is:", "Straight Lines", "√((4-1)^2 + (6-2)^2) = √(9+16) = 5.", "EASY", "5", "7", "√7", "25", "A"],
            ["Slope of line 2x + 3y + 5 = 0 is:", "Straight Lines", "y = (-2/3)x - 5/3. Slope is -2/3.", "EASY", "2/3", "-2/3", "3/2", "-3/2", "B"],
            ["Equation of line through (0,0) with slope 2 is:", "Straight Lines", "y - 0 = 2(x - 0) => y = 2x.", "EASY", "x = 2y", "y = 2x", "y = x+2", "2x+y=0", "B"],
            ["Two lines are perpendicular if the product of their slopes is:", "Straight Lines", "Fundamental property m1*m2 = -1.", "EASY", "1", "0", "-1", "2", "C"],
            ["Distance from origin to line 3x + 4y - 10 = 0 is:", "Straight Lines", "|-10| / √(3^2+4^2) = 10/5 = 2.", "MEDIUM", "2", "10", "√10", "5", "A"],
            ["Equation of x-axis is:", "Straight Lines", "On x-axis, y is always 0.", "EASY", "x=0", "y=0", "y=x", "x+y=0", "B"],
            ["Slope of line making 135° with positive x-axis is:", "Straight Lines", "tan 135° = -1.", "EASY", "1", "-1", "0", "Undefined", "B"],
            ["The centroid of triangle with vertices (1,1), (2,3), (3,5) is:", "Straight Lines", "((1+2+3)/3, (1+3+5)/3) = (2, 3).", "MEDIUM", "(2,3)", "(3,3)", "(2,4)", "(1,2)", "A"],
            ["Equation of line in intercept form is:", "Straight Lines", "x/a + y/b = 1.", "EASY", "y=mx+c", "x/a+y/b=1", "ax+by+c=0", "None", "B"],
            ["Angle between lines y=x and y=0 is:", "Straight Lines", "45°.", "EASY", "30°", "45°", "60°", "90°", "B"],

            # Conic Sections (73-82)
            ["Center and radius of x^2 + y^2 = 9 are:", "Conics", "(0,0) and √9 = 3.", "EASY", "(0,0), 9", "(0,0), 3", "(1,1), 3", "None", "B"],
            ["Focus of parabola y^2 = 4ax is:", "Conics", "Standard form focus is (a, 0).", "EASY", "(0, a)", "(a, 0)", "(-a, 0)", "(0, -a)", "B"],
            ["Length of latus rectum of y^2 = 12x is:", "Conics", "4a = 12.", "EASY", "3", "6", "12", "4", "C"],
            ["Eccentricity of a circle is:", "Conics", "Circle is a limiting case with e=0.", "EASY", "0", "1", "<1", ">1", "A"],
            ["Equation x^2/16 + y^2/9 = 1 represents:", "Conics", "Sum of squares with different denominators: Ellipse.", "EASY", "Circle", "Parabola", "Ellipse", "Hyperbola", "C"],
            ["Foci of x^2/25 + y^2/9 = 1 are:", "Conics", "a=5, b=3, c=√(25-9)=4. Foci (±4, 0).", "MEDIUM", "(±4,0)", "(0,±4)", "(±5,0)", "(0,±3)", "A"],
            ["Eccentricity of hyperbola x^2/a^2 - y^2/b^2 = 1 is:", "Conics", "e = √(1 + b^2/a^2) > 1.", "MEDIUM", "<1", "1", ">1", "0", "C"],
            ["Directrix of parabola x^2 = -8y is:", "Conics", "4a=8, a=2. Opens down, directrix is y=2.", "MEDIUM", "y=2", "y=-2", "x=2", "x=-2", "A"],
            ["Point (3,4) lies _____ the circle x^2+y^2=25:", "Conics", "3^2 + 4^2 = 25. Lies ON the circle.", "EASY", "Inside", "Outside", "On", "None", "C"],
            ["Equation of asymptotes of x^2/a^2 - y^2/b^2 = 1 are:", "Conics", "y = ±(b/a)x.", "HARD", "y=±x", "y=±(b/a)x", "y=±(a/b)x", "None", "B"],

            # 3D Geometry (83-88)
            ["Distance of point (1,2,3) from origin is:", "3D Geometry", "√(1^2+2^2+3^2) = √14.", "EASY", "6", "√14", "14", "3", "B"],
            ["Coordinates of mid-point of (2,3,4) and (4,5,6) are:", "3D Geometry", "((2+4)/2, (3+5)/2, (4+6)/2) = (3,4,5).", "EASY", "(3,4,5)", "(6,8,10)", "(1,1,1)", "None", "A"],
            ["Octant in which point (-1, 2, -3) lies is:", "3D Geometry", "x negative, y positive, z negative: 6th Octant.", "MEDIUM", "2nd", "4th", "6th", "8th", "C"],
            ["Equation of XY-plane is:", "3D Geometry", "On XY plane, z is always 0.", "EASY", "x=0", "y=0", "z=0", "x+y=0", "C"],
            ["A line makes equal angles with axes, its direction cosines are:", "3D Geometry", "l^2+m^2+n^2=1 => 3l^2=1 => l=±1/√3.", "MEDIUM", "1,1,1", "1/√3, 1/√3, 1/√3", "1/2, 1/2, 1/2", "None", "B"],
            ["Distance between (1,-1,3) and (2,3,5) is:", "3D Geometry", "√((2-1)^2 + (3-(-1))^2 + (5-3)^2) = √(1+16+4) = √21.", "MEDIUM", "√21", "21", "5", "3", "A"],

            # Limits & Derivatives (89-96)
            ["Limit as x->2 of (x^2-4)/(x-2) is:", "Calculus", "Lim (x+2)(x-2)/(x-2) = Lim (x+2) = 4.", "EASY", "2", "4", "0", "Undefined", "B"],
            ["Limit as x->0 of (sin x)/x is:", "Calculus", "Fundamental limit = 1.", "EASY", "0", "1", "Infinite", "None", "B"],
            ["Derivative of sin x is:", "Calculus", "d/dx(sin x) = cos x.", "EASY", "sin x", "cos x", "-cos x", "tan x", "B"],
            ["Derivative of x^10 is:", "Calculus", "10 * x^9.", "EASY", "x^9", "10x^9", "9x^10", "10x^11", "B"],
            ["Derivative of log x is:", "Calculus", "1/x.", "EASY", "x", "1/x", "e^x", "1", "B"],
            ["Derivative of e^x is:", "Calculus", "e^x remains e^x.", "EASY", "x*e^(x-1)", "log x", "e^x", "1", "C"],
            ["If y = sin(x^2), dy/dx is:", "Calculus", "Chain rule: cos(x^2) * 2x.", "MEDIUM", "cos(x^2)", "2x cos(x^2)", "2 sin x", "None", "B"],
            ["Derivative of tan x is:", "Calculus", "sec^2 x.", "EASY", "sec x", "sec^2 x", "cosec^2 x", "None", "B"],

            # Statistics & Probability (97-100)
            ["Mean of first 5 natural numbers is:", "Statistics", "(1+2+3+4+5)/5 = 15/5 = 3.", "EASY", "2", "3", "4", "2.5", "B"],
            ["If P(A) = 0.4, P(not A) is:", "Probability", "1 - 0.4 = 0.6.", "EASY", "0.4", "0.6", "0", "1", "B"],
            ["Probability of drawing an ace from a deck of 52 cards is:", "Probability", "4/52 = 1/13.", "EASY", "1/52", "4/52", "1/13", "1/4", "C"],
            ["Variance of a constant is:", "Statistics", "A constant does not vary, so variance is 0.", "EASY", "0", "1", "Constant", "None", "A"]
        ]

        # 3. Create Questions
        questions_to_create = []
        for q in raw_questions:
            questions_to_create.append(Question(
                skill=skill,
                text=q[0],
                concept_tag=q[1],
                explanation=q[2],
                difficulty=q[3],
                option_a=q[4],
                option_b=q[5],
                option_c=q[6],
                option_d=q[7],
                correct_option=q[8]
            ))

        with transaction.atomic():
            Question.objects.bulk_create(questions_to_create)
            self.stdout.write(self.style.SUCCESS(f"Successfully created {len(questions_to_create)} questions for '{skill.name}'"))
            
            # 4. Partition Questions into Sets
            sets_count = skill.partition_questions()
            self.stdout.write(self.style.SUCCESS(f"Partitioned questions into {sets_count} sets."))

