def consolidate_subject_data(student_subject_data):
    seen_subjects = set()
    consolidated_data = []

    for subject in student_subject_data:
        subject_name = subject['subject_name']
        
        # Check if the subject is already in the consolidated list
        if subject_name not in seen_subjects:
            seen_subjects.add(subject_name)
            consolidated_data.append(subject)
    
    return consolidated_data
